from __future__ import annotations
import datetime
import re
from enum import Enum
from medperf.exceptions import ExecutionError
from medperf import config
from medperf.ui.interface import UI
from pexpect import spawn
from pexpect.exceptions import TIMEOUT
from pydantic import BaseModel, Field
import logging
from typing import ClassVar
import yaml
import os
from functools import partial


class CWLStatus(Enum):
    success = "success"
    fail = "fail"
    started = "started"
    not_started = "not_started"
    not_applicable = "n/a"


class CWLEventTypes(Enum):
    start = "start"
    end = "end"
    other = "other"


class CWLTags(Enum):
    workflow = "workflow"
    step = "step"
    job = "job"


class CWLStep(BaseModel):
    name: str
    status: CWLStatus = Field(default=CWLStatus.not_started)
    start_time: datetime.datetime = None
    end_time: datetime.datetime = None
    cache_dir: str = None

    def update_status(self, cwl_info: CWLJobInfo):
        if cwl_info.type == CWLEventTypes.start:
            self.start_time = cwl_info.timestamp
            self.status = cwl_info.status
        elif cwl_info.type == CWLEventTypes.end:
            self.end_time = cwl_info.timestamp
            self.status = cwl_info.status

        if cwl_info.cache_dir is not None:
            self.cache_dir = cwl_info.cache_dir

    @property
    def elapsed_time(self):
        if self.start_time is None or self.end_time is None:
            return None
        return self.end_time - self.start_time


class CWLStepCollection(BaseModel):
    base_step_name: str
    steps: dict[str, CWLStep] = Field(default_factory=dict)
    total_number_of_steps: int = None  # Currently not available from logs

    _base_step_regex: ClassVar[re.Pattern] = re.compile(r"(.*)(?:_\d+)?")
    _start_time: datetime.datetime = None
    _end_time: datetime.datetime = None

    def get_current_completion(self):

        started = 0
        completed = 0
        error = 0
        for step_obj in self.steps.values():
            if step_obj.status == CWLStatus.success:
                started += 1
                completed += 1
            elif step_obj.status == CWLStatus.fail:
                started += 1
                error += 1
            elif step_obj.status == CWLStatus.started:
                started += 1

        try:
            fraction_completed = round(
                completed / started, 4
            )  # 2 decimal places as percentage
        except ZeroDivisionError:
            fraction_completed = 0.0  # Default before starting

        completion_dict = {
            "started": started,
            "completed": completed,
            "error": error,
            "fraction_completed": fraction_completed,
        }
        return completion_dict

    @property
    def number_of_steps(self):
        return self.total_number_of_steps or len(self.steps)

    def update_step(self, job_info: CWLJobInfo):
        name_to_update = job_info.job_name
        if name_to_update not in self.steps:
            self.steps[name_to_update] = CWLStep(name=name_to_update)

        step_obj = self.steps[name_to_update]
        step_obj.update_status(job_info)

    @property
    def start_time(self):
        start_times = (step.start_time for step in self.steps.values())
        if any(start_time is None for start_time in start_times):
            return None

        return min(start_times)

    @property
    def end_time(self):
        end_times = (step.end_time for step in self.steps.values())
        if any(end_time is None for end_time in end_times):
            return None

        return max(end_times)


class CWLEvent:
    """Based on https://github.com/inutano/cwl-log-generator/blob/master/lib/cwlevent.rb"""

    CWLTOOL_LOG_REGEX = re.compile(r"^(?:\[)?(.+?)\] (.+?) (?:\[(.+?)\])? (.+)$")
    CWLTOOL_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

    def __init__(self, log_line):
        regex_match = self.CWLTOOL_LOG_REGEX.match(log_line)
        try:
            timestamp_string, self.log_level, self.tag, self.contents = (
                regex_match.groups()
            )
            self.tag = self.tag.strip()
            self.contents = self.contents.strip()
            self.log_level = self.log_level.strip()
            # Set timestamp using the system's timezone. This is what the CWLTool logs do
            self.timestamp = datetime.datetime.strptime(
                timestamp_string, self.CWLTOOL_TIMESTAMP_FORMAT
            ).astimezone()

        except (TypeError, AttributeError):
            self.timestamp, self.log_level, self.tag, self.contents = [None] * 4

    def __repr__(self):
        return f"{self.__class__.__name__}(tag={self.tag}, log_level={self.log_level})"

    @property
    def is_cwltool_log_line(self):
        prop_list = [self.timestamp, self.log_level, self.tag, self.contents]
        return all(prop is not None for prop in prop_list)


class CWLInfoMessages:
    completed_success = "completed success"
    completed_fail = "completed permanentFail"
    start = "start"


class CWLEventInfo:
    def __init__(self, event: CWLEvent):
        if event.contents == CWLInfoMessages.start:
            self.type = CWLEventTypes.start
            self.status = CWLStatus.started
        elif event.contents == CWLInfoMessages.completed_success:
            self.type = CWLEventTypes.end
            self.status = CWLStatus.success
        elif event.contents == CWLInfoMessages.completed_fail:
            self.type = CWLEventTypes.end
            self.status = CWLStatus.fail
        else:
            self.type = CWLEventTypes.other
            self.status = CWLStatus.not_applicable
        self.timestamp = event.timestamp

    def __repr__(self):
        return f"{self.__class__.__name__}(status={self.status}, type={self.type}, timestamp={self.timestamp})"


class CWLWorkflowInfo(CWLEventInfo):
    """Currently only collects start/end times and status like the parent class"""

    pass


class CWLJobInfo(CWLEventInfo):

    job_regex = re.compile(r"^(?:job |step )(.*)$")
    cache_regex = re.compile(r"^.*cached(.*)in (.*)$")

    def __init__(self, event: CWLEvent):
        super().__init__(event=event)
        self.job_name = self.job_regex.match(event.tag).group(1)
        cache_match = self.cache_regex.match(event.contents)
        if cache_match:
            # self.type = CWLEventTypes.start  # TODO decouple from cache, may not be used
            # self.status = CWLStatus.started
            self.cache_dir = cache_match.group(1)
        else:
            self.cache_dir = None

    @classmethod
    def check_tag_for_job(cls, tag) -> bool:
        return bool(cls.job_regex.match(tag))


def read_terminal_line_from_proc(initial_line: str, proc: spawn) -> tuple[str, str]:
    complete_line = initial_line
    ANSI_LINE_START = "\x1b"

    while True:
        try:
            new_line: bytes = proc.readline()
        except TIMEOUT:
            logging.error("Process timed out")
            raise ExecutionError("Process timed out, logfile available at {logs_file}")

        new_line = new_line.decode("utf-8", "ignore")
        new_terminal_line_created = (
            new_line.startswith(ANSI_LINE_START) and complete_line
        )
        processes_finished = not proc.isalive()
        if new_terminal_line_created or processes_finished:
            return complete_line, new_line

        complete_line += new_line


class CWLExecutionMonitor:
    ansi_shell_characters_compiled_regex = re.compile(
        r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])"
    )
    job_prefix_regex = re.compile(r"^(.*?)(?:_\d+)?$")

    def __init__(
        self,
        cwl_exec_process: spawn,
        steps_to_monitor: list[str],
        report_file: str = None,
        update_interval_seconds: int = 60,
        output_logs: bool = False,
    ):
        self._cwl_process = cwl_exec_process
        self._step_names_to_monitor = steps_to_monitor
        self.update_interval = datetime.timedelta(seconds=update_interval_seconds)
        self.output_logs = output_logs
        self._step_name_to_step_collection = {
            step: CWLStepCollection(base_step_name=step)
            for step in self._step_names_to_monitor
        }
        self.steps = list(self._step_name_to_step_collection.values())
        self.workflow_execution_start = self.workflow_execution_end = (
            self.workflow_elapsed_time
        ) = None
        self.workflow_status = CWLStatus.not_started
        self._print_command = (
            config.ui if isinstance(config, UI) else partial(print, end="")
        )
        self.report_file = report_file
        if self.report_file:
            report_dir = os.path.normpath(os.path.dirname(self.report_file))
            if report_dir and not os.path.exists(report_dir):
                os.makedirs(report_dir, exist_ok=True)

            if not os.path.exists(self.report_file):
                self.update_report()

    def monitor(self):
        try:
            self._run_monitor()
        except (Exception, KeyboardInterrupt) as e:
            self.update_report()
            raise e

    def _run_monitor(self):
        next_line_start = ""
        must_stop = False
        last_update = None
        while not must_stop:

            complete_line, next_line_start = read_terminal_line_from_proc(
                next_line_start, self._cwl_process
            )
            if complete_line and self.output_logs:
                self._print_command(complete_line)
            elif not complete_line and not self._cwl_process.isalive():
                must_stop = True

            escaped_line = self.ansi_shell_characters_compiled_regex.sub(
                "", complete_line
            ).strip()

            potential_event = CWLEvent(escaped_line)
            if not potential_event.is_cwltool_log_line:
                continue

            if potential_event.tag == CWLTags.workflow.value:
                self.update_times_and_status(potential_event)
            elif CWLJobInfo.check_tag_for_job(potential_event.tag):
                self.update_step(potential_event)

            now = datetime.datetime.now()
            must_update = (last_update is None) or (
                now - last_update > self.update_interval
            )
            if must_update:
                last_update = now
                self.update_report()

        if self.workflow_execution_start and self.workflow_execution_end:
            self.workflow_elapsed_time = (
                self.workflow_execution_end - self.workflow_execution_start
            )

        self.update_report()

    def update_times_and_status(self, cwl_event: CWLEvent):
        workflow_info = CWLWorkflowInfo(cwl_event)
        if workflow_info.type == CWLEventTypes.start:
            self.workflow_execution_start = workflow_info.timestamp
            self.workflow_status = workflow_info.status

        elif workflow_info.type == CWLEventTypes.end:
            self.workflow_execution_end = workflow_info.timestamp
            self.workflow_status = workflow_info.status

    def update_step(self, cwl_event: CWLEvent):
        job_info = CWLJobInfo(cwl_event)

        try:
            collection_name_to_update = self.job_prefix_regex.match(
                job_info.job_name
            ).group(1)
        except AttributeError:  # if no match is found, use name as is
            collection_name_to_update = job_info.job_name

        try:
            collection_to_update = self._step_name_to_step_collection[
                collection_name_to_update
            ]
            collection_to_update.update_step(job_info)
        except KeyError:  # If a step wasn't mapped, do not update anything
            pass

    def update_report(self):
        if self.report_file is None:
            return  # If no report file is provided, there's no report to update

        report_data = {
            f"{step.base_step_name}": step.get_current_completion()
            for step in self.steps
        }

        with open(self.report_file, "w") as f:
            yaml.dump(report_data, f, sort_keys=False)
