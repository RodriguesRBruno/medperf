from typing import Callable

import medperf.config as config
from medperf.entities.interface import Entity
from medperf.entities.schemas import DeployableSchema
from medperf.enums import WorkflowTypes


class Workflow(Entity, DeployableSchema):
    """
    Class representing a Workflow

    Medperf platform may use a Workflow definition rather than a MLCube for complex
    Data Preparation pipelines.
    uses the MLCube container for components such as
    Dataset Preparation, Evaluation, and the Registered Models. MLCube
    containers are software containers (e.g., Docker and Singularity)
    with standard metadata and a consistent file-system level interface.
    """

    workflow_definition_file_url: str
    workflow_definition_file_hash: str
    workflow_type: WorkflowTypes

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

    # @property
    # def runner(self):
    #     if self._runner is None:
    #         self._runner = load_workflow_runner(self.parser, self.path)
    #     return self._runner

    def __init__(self, *args, **kwargs):
        """Creates a Workflow instance"""
        super().__init__(*args, **kwargs)
