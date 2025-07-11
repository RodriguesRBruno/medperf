from medperf.exceptions import MedperfException, InvalidWorkflowSpec
from .workflow_parser import WorkflowParser
from .cwl_parser import CWLParser
from medperf.enums import WorkflowTypes
import os
import yaml


def load_workflow_parser(workflow_config_path: str) -> WorkflowParser:
    if not os.path.exists(workflow_config_path):
        # Internal error
        raise MedperfException(f"{workflow_config_path} hasn't been downloaded yet.")

    with open(workflow_config_path) as f:
        workflow_config = yaml.safe_load(f)

    if workflow_config is None:
        raise InvalidWorkflowSpec(f"Empty workflow config file: {workflow_config_path}")

    if "workflow_type" not in workflow_config:
        raise InvalidWorkflowSpec(
            "Workflow config file should contain a 'workflow_type' field."
        )

    workflow_type = workflow_config["workflow_type"].lower()
    if workflow_type == WorkflowTypes.CWL.value:
        parser = CWLParser(workflow_config)
    else:
        allowed_workflows_list = [workflow.value for workflow in WorkflowTypes]
        allowed_workflows_string = ", ".join(allowed_workflows_list)
        raise InvalidWorkflowSpec(
            f"Invalid workflow type: {workflow_type}. Allowed types are: {allowed_workflows_string}"
        )
    parser.check_schema()
    return parser
