from dagster import (
    DynamicPartitionsDefinition,
    asset,
    sensor,
    SensorResult,
    RunRequest,
    AssetSelection,
    AssetKey,
)
import dagster as dg
import os
from dagster_docker import PipesDockerClient

# TODO standardize all these strings
subjects_partitions_def = DynamicPartitionsDefinition(name="subjects_timepoints")

workspace_dir = os.getenv("WORKSPACE_DIRECTORY")
project_dir = os.getenv("PROJECT_DIRECTORY")
data_dir = os.path.join(workspace_dir, "data")
input_dir = os.getenv("DAGSTER_INPUT_DATA_DIR")


def _mount_helper(host_dirs: list[str], container_dirs: list[str]):
    host_dir = os.path.join(*host_dirs)
    container_dir = os.path.join(*container_dirs)
    return f"{host_dir}:{container_dir}"


def _run_rano_docker(
    docker_pipes_client: PipesDockerClient,
    context: dg.AssetExecutionContext,
    docker_image: str,
    command: str,
    *command_args,
):

    return docker_pipes_client.run(
        image=docker_image,
        command=[command, *command_args],
        context=context,
        container_kwargs={
            "volumes": [
                _mount_helper(
                    host_dirs=[workspace_dir], container_dirs=["/", "workspace"]
                ),
                # TODO remove these after finalizing docker image
                _mount_helper(
                    host_dirs=[project_dir, "dagster_home"],
                    container_dirs=["/", "project", "dagster_home"],
                ),
                _mount_helper(host_dirs=[project_dir], container_dirs=["/", "project"]),
            ],
        },
    ).get_results()


@asset(partitions_def=subjects_partitions_def, code_version="0.0.1")
def make_partitions(context: dg.AssetExecutionContext):
    """
    First execution from the sensors only creates the partitions; following executions (ie the actual pipeline)
    will then be aggregated in the UI.
    """
    subject_partition = context.partition_key
    return subject_partition


@asset(
    partitions_def=subjects_partitions_def,
    code_version="0.0.1",
    automation_condition=dg.AutomationCondition.eager(),
    non_argument_deps={AssetKey(make_partitions.key.path)},
)
def make_csv(
    context: dg.AssetExecutionContext,
    docker_pipes_client: PipesDockerClient,
):
    subject_subir = context.partition_key

    res = _run_rano_docker(
        docker_pipes_client,
        context,
        "rano_docker_stages",
        "make_csv",
        "--subject-subdir",
        subject_subir,
    )

    return res


@asset(
    partitions_def=subjects_partitions_def,
    code_version="0.0.1",
    automation_condition=dg.AutomationCondition.eager(),
    non_argument_deps={AssetKey(make_csv.key.path)},
)
def convert_nifti(
    context: dg.AssetExecutionContext, docker_pipes_client: PipesDockerClient
):

    subject_subir = context.partition_key

    res = _run_rano_docker(
        docker_pipes_client,
        context,
        "rano_docker_stages",
        "convert_nifti",
        "--subject-subdir",
        subject_subir,
    )

    return res


@asset(
    partitions_def=subjects_partitions_def,
    code_version="0.0.1",
    automation_condition=dg.AutomationCondition.eager(),
    non_argument_deps={AssetKey(convert_nifti.key.path)},
)
def extract_brain(
    context: dg.AssetExecutionContext, docker_pipes_client: PipesDockerClient
):

    subject_subir = context.partition_key

    res = _run_rano_docker(
        docker_pipes_client,
        context,
        "rano_docker_stages",
        "extract_brain",
        "--subject-subdir",
        subject_subir,
    )

    return res


@asset(
    partitions_def=subjects_partitions_def,
    code_version="0.0.1",
    automation_condition=dg.AutomationCondition.eager(),
    non_argument_deps={AssetKey(convert_nifti.key.path)},
)
def extract_brain(
    context: dg.AssetExecutionContext, docker_pipes_client: PipesDockerClient
):

    subject_subir = context.partition_key

    res = _run_rano_docker(
        docker_pipes_client,
        context,
        "rano_docker_stages",
        "extract_brain",
        "--subject-subdir",
        subject_subir,
    )

    return res


@asset(
    partitions_def=subjects_partitions_def,
    code_version="0.0.1",
    automation_condition=dg.AutomationCondition.eager(),
    non_argument_deps={AssetKey(extract_brain.key.path)},
)
def extract_tumor(
    context: dg.AssetExecutionContext, docker_pipes_client: PipesDockerClient
):

    subject_subir = context.partition_key

    res = _run_rano_docker(
        docker_pipes_client,
        context,
        "rano_docker_stages",
        "extract_tumor",
        "--subject-subdir",
        subject_subir,
    )

    return res


def _get_subdirs(input_directory: str) -> list[str]:
    sub_directories = [
        os.path.join(input_directory, subdir) for subdir in os.listdir(input_directory)
    ]
    sub_directories = [
        subject_dir for subject_dir in sub_directories if os.path.isdir(subject_dir)
    ]
    return sub_directories


@sensor(
    asset_selection=AssetSelection.keys(
        make_partitions.key,
        make_csv.key,
        convert_nifti.key,
        extract_brain.key,
        extract_tumor.key,
    ),
    default_status=dg.DefaultSensorStatus.RUNNING,
)
def file_sensor(context: dg.SensorEvaluationContext):
    import os

    partitions = []

    subject_id_directories = _get_subdirs(input_dir)
    context.log.info(f"{subject_id_directories=}")
    for subject_id_directory in subject_id_directories:
        timepoint_directories = _get_subdirs(subject_id_directory)
        subject_timepoint_list_of_lists = [
            timepoint_directory.split(os.sep)[-2:]
            for timepoint_directory in timepoint_directories
        ]
        context.log.info(f"{subject_timepoint_list_of_lists=}")
        subject_slash_timepoint_list = [
            os.path.join(*subject_timepoint_list)
            for subject_timepoint_list in subject_timepoint_list_of_lists
        ]
        context.log.info(f"{subject_slash_timepoint_list}")
        partitions.extend(subject_slash_timepoint_list)
    context.log.info(f"{partitions=}")
    partitions = [
        partition
        for partition in partitions
        if not context.instance.has_dynamic_partition(
            subjects_partitions_def.name, partition
        )
    ]
    context.log.info(f"{partitions=}")
    return SensorResult(
        run_requests=[
            RunRequest(partition_key=partition, run_key=f"Auto Run Subject {partition}")
            for partition in partitions
        ],
        dynamic_partitions_requests=[
            subjects_partitions_def.build_add_request(partitions)
        ],
    )
