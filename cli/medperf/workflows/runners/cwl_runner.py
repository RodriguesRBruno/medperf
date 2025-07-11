from medperf.workflows.parsers.cwl_parser import CWLParser
from .workflow_runner import WorkflowRunner
from medperf import config
from medperf.enums import ContainerRuntimes
from medperf.utils import spawn_and_kill
from .cwl_utils_medperf import CWLExecutionMonitor
from cwl_utils.docker_extract import traverse


class CWLRunner(WorkflowRunner):
    """
    Class to execute CWL Workflows in MedPerf.
    The present implementation downloads a single workflow file and executes it with the run method.
    If a workflow is defined across multiple files, cwltool allows packing them into a single file
    via the command:
    cwltool --pack packed_workflow_name.json main_workflow_file_that_calls_other_workflows.cwl
    The resulting JSON file can then be executed similarly to any regular .cwl file, i.e:
    cwltool --outdir some_dir packed_workflow_name.json some_input.yaml
    """

    def __init__(self, workflow_parser: CWLParser, workflow_files_base_path: str):
        super().__init__(workflow_files_base_path=workflow_files_base_path)
        self._workflow_file = None  # Set by download method
        self._parser = workflow_parser

    def download_container_images(self):
        workflow_obj = self._parser.workflow_obj
        steps_generator = traverse(workflow_obj)

        for workflow_step in steps_generator:
            pass

    @property
    def workflow_output_json(self) -> str:
        return "workflow_output.json"

    @property
    def cwl_runner(self) -> str:
        return config.cwl_runner

    def _run_and_monitor_cwl(
        self,
        cmd,
        logs_file: str = None,
        report_file: str = None,
        output_logs: bool = False,
    ):
        with spawn_and_kill(cmd=cmd, logfile=logs_file, timeout=None) as proc_wrapper:
            proc = proc_wrapper.proc
            monitor = CWLExecutionMonitor(
                proc,
                steps_to_monitor=self._parser.steps,
                report_file=report_file,
                output_logs=output_logs,
            )
            monitor.monitor()

    def run(
        self,
        inputs_file: str,
        output_directory: str,
        cache_folder: str = None,
        output_logs: str = None,
        timeout: int = None,
    ):
        # TODO maybe add validation for inputs file? We can get a template via cwl-runner --make-template workflow_file.cwl

        base_args = [
            self.cwl_runner,
            "--outdir",
            output_directory,
            "-w",
            self.workflow_output_json,
        ]

        optional_args = []
        if cache_folder is not None:
            optional_args.extend(["--cachedir", cache_folder])

        if config.platform.lower() == ContainerRuntimes.singularity.lower():
            optional_args.append["--singularity"]

        final_args = [self._workflow_file, inputs_file]

        cwl_command = [*base_args, *optional_args, *final_args]
        self._run_and_monitor_cwl(
            cmd=cwl_command, logs_file=None, report_file=None, output_logs=output_logs
        )
