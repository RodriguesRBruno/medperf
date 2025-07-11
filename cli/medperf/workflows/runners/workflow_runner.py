from abc import ABC, abstractmethod
from medperf.workflows.parsers.workflow_parser import WorkflowParser


class WorkflowRunner(ABC):

    def __init__(self, workflow_parser: WorkflowParser, workflow_files_base_path: str):
        self.workflow_files_base_path = workflow_files_base_path
        self.workflow_parser = workflow_parser

    @abstractmethod
    def download_container_images(self):
        pass

    @abstractmethod
    def run(
        self,
        cache_folder: str = None,
        output_logs: str = None,
        timeout: int = None,
    ):
        pass
