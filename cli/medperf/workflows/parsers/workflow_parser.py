from abc import ABC, abstractmethod
from medperf.enums import ContainerRuntimes, WorkflowTypes


class WorkflowParser(ABC):

    def __init__(self, workflow_config: dict[str, str]):
        self._workflow_config = workflow_config

    @abstractmethod
    def download_workflow(
        self,
        expected_file_hash: str,
        download_timeout: int = None,
        get_hash_timeout: int = None,
    ):
        pass

    @property
    @abstractmethod
    def steps(self):
        pass

    @property
    def allowed_runners(self) -> list[str]:
        """
        Can be overriden if we add workflows that support different container runtimes in the future
        """
        return [ContainerRuntimes.docker.value, ContainerRuntimes.singularity.value]

    @property
    @abstractmethod
    def workflow_filename(self) -> str:
        pass

    @property
    @abstractmethod
    def workflow_type(self) -> WorkflowTypes:
        pass

    @property
    @abstractmethod
    def workflow_steps(self) -> list[str]:
        pass

    @abstractmethod
    def get_setup_args(self):
        pass

    @abstractmethod
    def check_schema(self):
        pass

    @abstractmethod
    def is_report_specified(self):
        pass

    @abstractmethod
    def is_metadata_specified(self):
        pass
