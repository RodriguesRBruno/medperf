from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.singularity.operators.singularity import SingularityOperator
from docker.types import Mount
import os


def _mount_helper(host_dirs: list[str], container_dirs: list[str]):
    host_dir = os.path.join(*host_dirs)
    container_dir = os.path.join(*container_dirs)
    return Mount(source=host_dir, target=container_dir, type="bind")


def _docker_operator_factory(command_name: str, *command_args: str) -> DockerOperator:
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
        image="rano_docker_stages",
        command=[command_name, *command_args],
        mounts=mounts,
        task_id=command_name,
        auto_remove="success",
    )


def make_pipeline_for_subject(subject_subdir):
    _PIPELINE_STAGES = ["make_csv", "convert_nifti", "extract_brain", "extract_tumor"]

    prev_task = None
    for stage in _PIPELINE_STAGES:
        curr_task = _docker_operator_factory(stage, "--subject-subdir", subject_subdir)
        if prev_task is not None:
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
