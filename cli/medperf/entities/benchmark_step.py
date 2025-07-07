import os
from typing import List, Optional, Union
from pydantic import Field
from abc import abstractmethod

from medperf.entities.interface import Entity
from medperf.entities.schemas import DeployableSchema
from medperf.exceptions import InvalidEntityError
import medperf.config as config


class BenchmarkStep(Entity, DeployableSchema):
    """
    Class representing a Benchmark Step (Data Preparation, Evaluation or Metrics)

    At time of writing, each step could be implemented as one of:
    - MLCube
    - Generic Container
    - Workflow

    The MLCube and Generic Container implementations use the Cube subclass, while the Workflow
    implementation uses the workflow subclass
    """

    additional_files_tarball_url: Optional[str] = Field(None, alias="tarball_url")
    additional_files_tarball_hash: Optional[str] = Field(None, alias="tarball_hash")
    metadata: dict = Field(default_factory=dict)
    user_metadata: dict = Field(default_factory=dict)

    @abstractmethod
    def download_config_files(self):
        pass

    @abstractmethod
    def download_run_files(self):
        pass

    @abstractmethod
    def run(
        self,
        task: str,
        output_logs: str = None,
        timeout: int = None,
        mounts: dict = {},
        env: dict = {},
        ports: list = [],
        disable_network: bool = True,
    ):
        pass

    @abstractmethod
    def is_report_specified(self):
        pass

    @abstractmethod
    def is_metadata_specified(self):
        pass

    @classmethod
    def get_benchmarks_associations(cls, uid: int) -> List[dict]:
        raise NotImplementedError

    @property
    @abstractmethod
    def runner(self):
        pass

    @property
    @abstractmethod
    def config_file(self):
        pass

    @staticmethod
    @abstractmethod
    def remote_prefilter(filters: dict):
        pass

    def __init__(self, *args, **kwargs):
        """Creates a Cube instance

        Args:
            cube_desc (Union[dict, CubeModel]): MLCube Instance description
        """
        super().__init__(*args, **kwargs)

        self.additiona_files_folder_path = None
        self.additiona_files_folder_path = os.path.join(
            self.path, config.additional_path
        )
        self._runner = None

    @property
    def local_id(self):
        return self.name

    @classmethod
    def get(
        cls,
        uid: Union[str, int],
        local_only: bool = False,
        valid_only: bool = True,
    ) -> "BenchmarkStep":
        """Retrieves and creates a BenchmarkStep instance from the comms. If cube already exists
        inside the user's computer then retrieves it from there.

        Args:
            valid_only: if to raise an error in case of invalidated BenchmarkStep
            cube_uid (str): UID of the cube.

        Returns:
            BenchmarkStep : a BenchmarkStep instance with the retrieved data.
        """

        step = super().get(uid, local_only)
        if not step.is_valid and valid_only:
            raise InvalidEntityError("The requested container is marked as INVALID.")
        step.download_config_files()
        return step

    def display_dict(self):
        return {
            "UID": self.identifier,
            "Name": self.name,
            "Config File": self.config_file,
            "State": self.state,
            "Created At": self.created_at,
            "Registered": self.is_registered,
        }
