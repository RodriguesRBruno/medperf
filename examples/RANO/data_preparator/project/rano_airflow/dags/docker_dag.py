from __future__ import annotations
import os
from airflow.decorators import task_group
from airflow.models.dag import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.singularity.operators.singularity import SingularityOperator

from docker.types import Mount

workspace_dir = os.getenv("WORKSPACE_DIRECTORY")
root_preparator_dir = os.getenv("ROOT_PREP_DIR")
print(f"{workspace_dir=}")
print(f"{root_preparator_dir=}")

data_dir = os.path.join(workspace_dir, "data")
input_dir = os.path.join(workspace_dir, "input_data")


def _mount_helper(host_dirs: list[str], container_dirs: list[str]):
    host_dir = os.path.join(root_preparator_dir, *host_dirs)
    container_dir = os.path.join(*container_dirs)
    return Mount(source=host_dir, target=container_dir, type="bind")


def _get_subdirs(input_directory: str) -> list[str]:
    sub_directories = [
        os.path.join(input_directory, subdir) for subdir in os.listdir(input_directory)
    ]
    sub_directories = [
        subject_dir for subject_dir in sub_directories if os.path.isdir(subject_dir)
    ]
    return sub_directories


def _docker_operator_factory(
    subject_id_slash_timepoint: str, command_name: str, *command_args: str
) -> DockerOperator:
    mounts = [
        _mount_helper(
            host_dirs=["mlcube", "workspace"], container_dirs=["/", "workspace"]
        ),
        _mount_helper(host_dirs=["project"], container_dirs=["/", "project"]),
    ]

    return DockerOperator(
        image="rano_docker_stages",
        command=[command_name, *command_args],
        mounts=mounts,
        task_id=command_name,  # f"{command_name}_{subject_id_slash_timepoint.replace('/', '_')}",
        auto_remove="success",
    )


def _make_pipeline_for_subject(subject_id_slash_timepoint: str):
    _PIPELINE_STAGES = ["make_csv", "convert_nifti", "extract_brain", "extract_tumor"]

    # TODO make a proper way to ensure only legal characters in this id
    subject_id_underline_timepoint = subject_id_slash_timepoint.replace(
        "/", "_"
    ).replace(".", "-")

    @task_group(
        group_id=subject_id_underline_timepoint,
    )
    def make_pipeline():
        prev_task = None
        for stage in _PIPELINE_STAGES:
            curr_task = _docker_operator_factory(
                subject_id_slash_timepoint,
                stage,
                "--subject-subdir",
                subject_id_slash_timepoint,
            )
            if prev_task is not None:
                prev_task >> curr_task
            prev_task = curr_task

    return make_pipeline()


def _make_pipelines_for_all_subjects():
    subject_slash_timepoint_list = [
        "AAAC_1/2008.03.31",
        "AAAC_1/2012.01.02",
        "AAAC_2/2001.01.01",
    ]
    for subject_slash_timepoint in subject_slash_timepoint_list:
        _make_pipeline_for_subject(subject_slash_timepoint)


# TODO how to do this if Airflow doesn't even see the data?
#  subject_id_directories = _get_subdirs(input_dir)
#  for subject_id_directory in subject_id_directories:
#      timepoint_directories = _get_subdirs(subject_id_directory)
#      subject_timepoint_list_of_lists = [
#          timepoint_directory.split(os.sep)[-2:]
#          for timepoint_directory in timepoint_directories
#      ]
#      subject_slash_timepoint_list = [
#          os.path.join(*subject_timepoint_list)
#          for subject_timepoint_list in subject_timepoint_list_of_lists
#      ]

#      for subject_slash_timepoint in subject_slash_timepoint_list:
#          _make_pipeline_for_subject(subject_slash_timepoint)


prev_task = curr_task = None
# TODO customize Docker Compose to install Singularity provider; not installed by default
with DAG(
    dag_id=f"rano_pipeline",
    dag_display_name="RANO Pipeline",
    catchup=True,
) as dag:
    _make_pipelines_for_all_subjects()
