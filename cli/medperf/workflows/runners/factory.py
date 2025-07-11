from .cwl_runner import CWLRunner

from medperf.enums import WorkflowTypes
from medperf.exceptions import InvalidArgumentError
from medperf import config

from medperf.workflows.parsers.workflow_parser import WorkflowParser
from .workflow_runner import WorkflowRunner


def load_workflow_runner(
    workflow_config_parser: WorkflowParser, workflow_files_base_path: str
) -> WorkflowRunner:
    if config.platform not in workflow_config_parser.allowed_runners:
        raise InvalidArgumentError(f"Cannot run this workflow with {config.platform}")

    if workflow_config_parser.workflow_type == WorkflowTypes.CWL:
        return CWLRunner(
            workflow_parser=workflow_config_parser,
            workflow_files_base_path=workflow_files_base_path,
        )
