from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.singularity.operators.singularity import SingularityOperator
from airflow.operators.empty import EmptyOperator
from docker.types import Mount
import os


def _mount_helper(host_dirs: list[str], container_dirs: list[str]):
    host_dir = os.path.join(*host_dirs)
    container_dir = os.path.join(*container_dirs)
    return Mount(source=host_dir, target=container_dir, type="bind")


def docker_operator_factory(
    command_name: str,
    *command_args: str,
    task_id: str = None,
    task_display_name: str = None,
) -> DockerOperator:

    workspace_host_dir = os.getenv("WORKSPACE_DIRECTORY")
    project_dir = os.getenv("PROJECT_DIRECTORY")

    task_id = task_id or command_name
    task_display_name = task_display_name or task_id

    mounts = [
        _mount_helper(
            host_dirs=[workspace_host_dir], container_dirs=["/", "workspace"]
        ),
        # TODO remove this after adjusting Docker image
        _mount_helper(host_dirs=[project_dir], container_dirs=["/", "project"]),
    ]

    return DockerOperator(
        image="rano_docker_stages",
        command=[command_name, *command_args],
        mounts=mounts,
        task_id=task_id,
        task_display_name=task_display_name,
        auto_remove="success",
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
        "make_csv",
        "convert_nifti",
        "extract_brain",
        "extract_tumor",
        "manual_annotation",
    ]
    _UNIMPLEMENTED_STAGES = ["segment_comparison"]
    prev_task = None
    for stage in _PIPELINE_STAGES:
        curr_task = docker_operator_factory(stage, "--subject-subdir", subject_subdir)
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
