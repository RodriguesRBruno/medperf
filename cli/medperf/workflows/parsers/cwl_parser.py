from .workflow_parser import WorkflowParser
from medperf.exceptions import InvalidWorkflowSpec
from medperf.enums import WorkflowTypes
import os
from medperf.comms.entity_resources import resources
from medperf.workflows.parsers.cwl_utils import get_tools
from cwl_utils.parser import load_document_by_uri


class CWLParser(WorkflowParser):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._workflow_obj = None
        self._steps = None

    @property
    def workflow_file_name(self) -> str:
        return "workflow.cwl"

    @property
    def steps(self):
        if self._steps is None:
            self._steps = get_tools(self._workflow_obj)
        return self._steps

    @property
    def workflow_obj(self):
        if self._workflow_obj is None:
            self._workflow_obj = load_document_by_uri(self._workflow_file)
        return self._workflow_obj

    @property
    def workflow_type(self) -> WorkflowTypes:
        return WorkflowTypes.CWL

    @property
    def get_setup_args(self):
        return self._workflow_config["workflow_file"]

    def check_schema(self):
        if "workflow_file" not in self._workflow_config:
            raise InvalidWorkflowSpec(
                "CWL workflow config should have a 'workflow_file' field."
            )

    def download_workflow(
        self,
        expected_file_hash: str,
        download_timeout: int = None,
        get_hash_timeout: int = None,
    ):
        workflow_url = self.get_setup_args()
        workflow_file_path = os.path.join(
            self._workflow_files_base_path, self.workflow_file_name
        )
        self._workflow_file, workflow_hash = resources.get_workflow_file(
            url=workflow_url,
            workflow_file_absolute_path=workflow_file_path,
            expected_hash=expected_file_hash,
        )

        return workflow_hash

    # TODO properly implement this logic
    def is_report_specified(self):
        return True  # Can always deliver report, but maybe it should be optional?

    def is_metadata_specified(self):
        return False
