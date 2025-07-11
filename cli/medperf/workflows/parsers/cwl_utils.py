from cwl_utils.parser import (
    load_document_by_uri,
    Workflow,
    CommandLineTool,
    ExpressionTool,
    WorkflowStep,
    WorkflowTypes,
)
from typing import Union

ToolType = Union[CommandLineTool, ExpressionTool]


def get_tools(
    cwl_workflow: Workflow, base_list: list[str] = None, step_id: str = None
) -> list[str]:
    """
    Gets all the names of all Tools (CommandLineTools or ExpressionTools) called by a given CWL Workflow.
    Subworkflows are NOT included in the result!
    """
    tool_list = []
    current_steps: list[WorkflowStep] = cwl_workflow.steps

    for step in current_steps:
        step_id = step.id.rsplit("#", maxsplit=1)[-1]
        possible_workflow = load_document_by_uri(step.run)

        if not isinstance(possible_workflow, WorkflowTypes):
            tool_list.append(step_id)
            continue

        steps_from_step = get_tools(
            cwl_workflow=possible_workflow, base_list=base_list, step_id=step_id
        )
        filtered_steps = [step for step in steps_from_step if step not in tool_list]
        tool_list.extend(filtered_steps)

    return tool_list


if __name__ == "__main__":
    uri = "/Users/brunorodrigues/MLCommons/medperf_workflows/pipeline_examples/rano/cwl/workflows/rano_workflow.cwl"
    workflow = load_document_by_uri(uri)
    tools = get_tools(workflow)
    b = 1
