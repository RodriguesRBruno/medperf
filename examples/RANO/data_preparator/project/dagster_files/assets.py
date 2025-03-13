from dagster import (
    DynamicPartitionsDefinition,
    asset,
    sensor,
    SensorResult,
    RunRequest,
    AssetSelection,
    Output,
    DataVersion,
)
import dagster as dg
import os


# TODO standardize all these strings
subjects_partitions_def = DynamicPartitionsDefinition(name="subjects_timepoints")

workspace_dir = os.getenv("DATA_DIRECTORY")
data_dir = os.path.join(workspace_dir, "data")
input_dir = os.path.join(workspace_dir, "input_data")


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
)
def make_csv(context: dg.AssetExecutionContext, make_partitions):
    from project.stages.get_csv import (
        AddToCSV,
    )

    subject_subdir = make_partitions
    output_csv_dir = os.path.join(data_dir, "csv", subject_subdir)
    os.makedirs(output_csv_dir, exist_ok=True)
    output_csv = os.path.join(output_csv_dir, "data.csv")
    out_dir = os.path.join(data_dir, "validated")
    csv_creator = AddToCSV(
        input_dir=input_dir,
        output_csv=output_csv,
        out_dir=out_dir,
        prev_stage_path=input_dir,  # TODO validate this
    )
    csv_creator.execute(context.partition_key)
    return Output(
        output_csv, data_version=DataVersion("1")
    )  # TODO formalize data version (hash, file data, etc)


@asset(
    partitions_def=subjects_partitions_def,
    code_version="0.0.1",
    automation_condition=dg.AutomationCondition.eager(),
)
def convert_nifti(context: dg.AssetExecutionContext, make_csv):
    from project.stages.nifti_transform import NIfTITransform

    csv_path = make_csv
    output_path = os.path.join(data_dir, "nifti")
    metadata_path = os.path.join(data_dir, "metadata")
    data_out = os.path.join(data_dir, "data")
    os.makedirs(output_path, exist_ok=True)
    os.makedirs(metadata_path, exist_ok=True)

    nifti_transform = NIfTITransform(
        data_csv=csv_path,
        out_path=output_path,
        prev_stage_path=input_dir,  # TODO validate this
        metadata_path=metadata_path,
        data_out=data_out,
    )
    nifti_transform.execute(context.partition_key)
    return Output(output_path)  # TODO validate proper outputpath here and data version


automation_sensor = dg.AutomationConditionSensorDefinition(
    name="automation_sensor",
    target="*",
    default_status=dg.DefaultSensorStatus.RUNNING,
    minimum_interval_seconds=1,
)


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
