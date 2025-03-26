from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.singularity.operators.singularity import SingularityOperator
from airflow.operators.empty import EmptyOperator
from docker.types import Mount
import os

class RANOStage:
    def __init__(self, command: str, *command_args, task_id: str = None, task_display_name: str = None,
                 **operator_kwargs):
        self.command = command
        self.command_args = command_args
        self.task_id = task_id or self.command
        self.task_display_name = (task_display_name or self.task_id) or self.command
        self.operator_kwargs = operator_kwargs

def _mount_helper(host_dirs: list[str], container_dirs: list[str]):
    host_dir = os.path.join(*host_dirs)
    container_dir = os.path.join(*container_dirs)
    return Mount(source=host_dir, target=container_dir, type="bind")


def docker_operator_factory(
    rano_stage: RANOStage
) -> DockerOperator:

    workspace_host_dir = os.getenv("WORKSPACE_DIRECTORY")
    project_dir = os.getenv("PROJECT_DIRECTORY")

    mounts = [
        _mount_helper(
            host_dirs=[workspace_host_dir], container_dirs=["/", "workspace"]
        ),
        # TODO remove this after adjusting Docker image
        _mount_helper(host_dirs=[project_dir], container_dirs=["/", "project"]),
    ]

    return DockerOperator(
        image="rano_docker_stages_v3",
        command=[rano_stage.command, *rano_stage.command_args],
        mounts=mounts,
        task_id=rano_stage.task_id,
        task_display_name=rano_stage.task_display_name,
        auto_remove="success",
        **rano_stage.operator_kwargs
    )


def dummy_operator_factory(
    dummy_id: str,
    dummy_display_name: str = None,
    doc_md="STAGE NOT YET IMPLEMENTED, DUMMY FOR DEMO PURPOSES",
):
    dummy_display_name = dummy_display_name or f"DUMMY {dummy_id}"
    return EmptyOperator(
        task_id=dummy_id, task_display_name=dummy_display_name, doc_md=doc_md
    )


def make_pipeline_for_subject(subject_subdir):
    _PIPELINE_STAGES = [
        RANOStage("make_csv", "--subject-subdir", subject_subdir, task_display_name='Make CSV'),
        RANOStage("convert_nifti", "--subject-subdir", subject_subdir, task_display_name='Convert to NIfTI'),
        RANOStage("extract_brain", "--subject-subdir", subject_subdir, task_display_name='Extract Brain'),
        RANOStage("extract_tumor", "--subject-subdir", subject_subdir, task_display_name='Extract Tumor'),
        RANOStage("manual_annotation", "--subject-subdir", subject_subdir, task_display_name='Mannual Annotation'),
    ]
    _UNIMPLEMENTED_STAGES = ["segment_comparison"]
    prev_task = None
    for stage in _PIPELINE_STAGES:
        curr_task = docker_operator_factory(stage)
        if prev_task is not None:
            prev_task >> curr_task
        prev_task = curr_task

    for unimplemented_stage in _UNIMPLEMENTED_STAGES:
        curr_task = dummy_operator_factory(unimplemented_stage)
        prev_task >> curr_task
        prev_task = curr_task


def create_legal_id(subject_slash_timepoint, restrictive=False):
    import re

    if restrictive:
        legal_chars = "A-Za-z0-9_-"
    else:
        egal_chars = "A-Za-z0-9_.~:+-"
    legal_id = re.sub(rf"[^{legal_chars}]", "_", subject_slash_timepoint)
    return legal_id


def read_subject_directories():
    INPUT_DATA_DIR = os.getenv("AIRFLOW_INPUT_DATA_DIR")

    subject_id_timepoint_directories = []

    for subject_id_dir in os.listdir(INPUT_DATA_DIR):
        subject_complete_dir = os.path.join(INPUT_DATA_DIR, subject_id_dir)

        for timepoint_dir in os.listdir(subject_complete_dir):
            subject_id_timepoint_dir = os.path.join(subject_id_dir, timepoint_dir)
            subject_id_timepoint_directories.append(subject_id_timepoint_dir)

    return subject_id_timepoint_directories
