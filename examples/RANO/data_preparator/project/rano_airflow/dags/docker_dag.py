from __future__ import annotations
import os
from airflow.decorators import task_group
from airflow.models.dag import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.singularity.operators.singularity import SingularityOperator
from airflow.models.param import Param

from docker.types import Mount

workspace_host_dir = os.getenv("WORKSPACE_DIRECTORY")
project_dir = os.getenv("PROJECT_DIRECTORY")


def _mount_helper(host_dirs: list[str], container_dirs: list[str]):
    host_dir = os.path.join(*host_dirs)
    container_dir = os.path.join(*container_dirs)
    return Mount(source=host_dir, target=container_dir, type="bind")


def _docker_operator_factory(command_name: str, *command_args: str) -> DockerOperator:
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


def _make_pipeline_for_subject():
    _PIPELINE_STAGES = ["make_csv", "convert_nifti", "extract_brain", "extract_tumor"]

    prev_task = None
    for stage in _PIPELINE_STAGES:
        curr_task = _docker_operator_factory(
            stage,
            "--subject-subdir",
            "{{ params.subject_subdir}}",
        )
        if prev_task is not None:
            prev_task >> curr_task
        prev_task = curr_task


prev_task = curr_task = None

with DAG(
    dag_id="rano_pipeline",
    dag_display_name="RANO Pipeline",
    catchup=True,
    params={
        "subject_subdir": Param("XXXX/YYYY.MM.DD", type="string"),
    },
    is_paused_upon_creation=False,
) as dag:
    _make_pipeline_for_subject()
