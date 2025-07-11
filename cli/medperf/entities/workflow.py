from typing import Callable, Optional
import os
import shutil

import medperf.config as config
from medperf.entities.benchmark_step import BenchmarkStep
from medperf.exceptions import InvalidEntityError
from medperf.workflows.runners.factory import load_workflow_runner
from medperf.workflows.parsers.factory import load_workflow_parser
from medperf.comms.entity_resources import resources


from medperf.workflows.parsers.workflow_parser import WorkflowParser
from medperf.workflows.runners.workflow_runner import WorkflowRunner


class Workflow(BenchmarkStep):
    """
    Class representing a Workflow

    Medperf platform may use a Workflow definition rather than a MLCube for complex
    Data Preparation pipelines.
    uses the MLCube container for components such as
    Dataset Preparation, Evaluation, and the Registered Models. MLCube
    containers are software containers (e.g., Docker and Singularity)
    with standard metadata and a consistent file-system level interface.
    """

    workflow_config_file_url: str
    workflow_config_file_hash: Optional[str]
    workflow_hash: Optional[str]
    container_hashes: dict[str, str]

    @staticmethod
    def get_type() -> str:
        return "workflow"

    @staticmethod
    def get_storage_path() -> str:
        raise config.workflows_folder

    @staticmethod
    def get_comms_retriever() -> Callable[[int], dict]:
        return config.comms.get_workflow_metadata

    @staticmethod
    def get_metadata_filename() -> str:
        return config.workflow_metadata_filename

    @staticmethod
    def get_comms_uploader() -> Callable[[dict], dict]:
        return config.comms.upload_workflow

    @property
    def local_id(self):
        return self.name

    @property
    def parser(self) -> WorkflowParser:
        if self._parser is None:
            self._parser = load_workflow_parser(self.workflow_config_file)
        return self._parser

    @property
    def runner(self) -> WorkflowRunner:
        if self._runner is None:
            self._runner = load_workflow_runner(self.parser, self.workflow_config_file)
        return self._runner

    def __init__(self, *args, **kwargs):
        """Creates a Workflow instance"""
        super().__init__(*args, **kwargs)
        self.workflow_config_file = os.path.join(self.path, config.workflow_filename)

    def download_workflow(self):
        workflow_file, file_hash = resources.get_workflow_config(
            url=self.workflow_config_file_url,
            workflow_dir=self.path,
            expected_hash=self.workflow_config_file_hash,
        )
        self.workflow_config_file = workflow_file
        self.workflow_config_file_hash = file_hash

    def download_config_files(self):
        try:
            self.download_workflow()
        except InvalidEntityError as e:
            raise InvalidEntityError(f"Workflow {self.name} config file: {e}")

    def download_run_files(self):
        try:
            self.download_additional()

        except InvalidEntityError as e:
            raise InvalidEntityError(f"Workflow {self.name} additional files: {e}")

        self.workflow_hash = self.parser.download_workflow(
            expected_file_hash=self.workflow_hash,
            download_timeout=config.workflow_configure_timeout,
            get_hash_timeout=config.workflow_inspect_timeout,
        )

        self.container_hashes = self.runner.download_container_images(
            expected_hashes=self.container_hashes,
            download_timeout=config.mlcube_configure_timeout,
            get_hash_timeout=config.mlcube_inspect_timeout,
        )

    def run(
        self,
        use_cache: bool = True,
        remove_cache_after_completion: bool = True,
        output_logs: str = None,
        timeout: int = None,
    ):
        os.makedirs(self.additiona_files_folder_path, exist_ok=True)
        cache_path = os.path.join(self.path, config.workspace_path, config.cache_path)
        if use_cache:
            if not os.path.exists(cache_path):
                os.makedirs(cache_path)
            cache_to_use = cache_path
        else:
            cache_to_use = None

        self.runner.run(
            cache_folder=cache_to_use, output_logs=output_logs, timeout=timeout
        )

        if use_cache and remove_cache_after_completion and os.path.isdir(cache_path):
            shutil.rmtree(cache_path)

    def is_report_specified(self):
        return self.parser.is_report_specified

    def is_metadata_specified(self):
        return self.parser.is_metadata_specified
