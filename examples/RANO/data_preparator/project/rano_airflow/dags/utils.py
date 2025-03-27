from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.singularity.operators.singularity import SingularityOperator
from airflow.operators.empty import EmptyOperator
from airflow.sensors.filesystem import FileSensor
from airflow.utils.trigger_rule import TriggerRule
from airflow.decorators import task
from docker.types import Mount
import os
from airflow.models.dagrun import DagRun
from airflow.models.dag import DAG
from airflow.models.taskinstance import TaskInstance
from airflow.utils.session import provide_session, NEW_SESSION
from airflow.utils.state import State
from airflow.utils.edgemodifier import Label
from airflow.exceptions import AirflowSkipException
import json


class RANOTaskIDs:
    CREATE_REPORT = "create_report"
    MAKE_CSV = "make_csv"
    CONVERT_NIFTI = "convert_nifti"
    EXTRACT_BRAIN = "extract_brain"
    EXTRACT_TUMOR = "extract_tumor"
    UPDATE_REPORT_AFTER_MANUAL = "update_report_after_manual"
    SEGMENT_COMPARISON = "segmentation_comparison"
    SEGMENTATIONS_VALIDATED = "segmentations_validated"
    VALIDATE_SEGMENTATIONS_STATE = "validate_state"
    CHECK_BRAIN_MASK = "check_brain_mask"
    BRAIN_MASK_CHANGED_BRANCH = "brain_mask_changed"
    CLEAR_RETURN_TO_BRAIN_EXTRACT = "clear_return_to_brain_extract"
    RETURN_TO_BRAIN_EXTRACT = "return_to_brain_extract"
    CLEAR_RETURN_TO_SEGMENTATIONS_VALIDATED = "clear_return_to_segmentations_validated"
    RETURN_TO_SEGMENTATIONS_VALIDATED = "return_to_segmentations_validated"
    CONFIRMATION_STAGE = "confirmation_stage"
    CONSOLIDATION_STAGE = "consolidation_stage"


class RANOStage:
    def __init__(
        self,
        command: str,
        *command_args,
        task_id: str = None,
        task_display_name: str = None,
        **operator_kwargs,
    ):
        self.command = command
        self.command_args = command_args
        self.task_id = task_id or self.command
        self.task_display_name = (task_display_name or self.task_id) or self.command
        self.operator_kwargs = operator_kwargs


def _mount_helper(host_dirs: list[str], container_dirs: list[str]):
    host_dir = os.path.join(*host_dirs)
    container_dir = os.path.join(*container_dirs)
    return Mount(source=host_dir, target=container_dir, type="bind")


def docker_operator_factory(rano_stage: RANOStage) -> DockerOperator:

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
        **rano_stage.operator_kwargs,
    )


def dummy_operator_factory(
    dummy_id: str,
    dummy_display_name: str = None,
    doc_md="STAGE NOT YET IMPLEMENTED, DUMMY FOR DEMO PURPOSES",
    **operator_kwargs,
):
    dummy_display_name = dummy_display_name or f"DUMMY {dummy_id}"
    return EmptyOperator(
        task_id=dummy_id,
        task_display_name=dummy_display_name,
        doc_md=doc_md,
        **operator_kwargs,
    )


@provide_session
def _clear_task(
    task_id: str,
    task_dag: DAG,
    dag_run: DagRun,
    include_downstream: bool = True,
    session=NEW_SESSION,
):
    """
    Clears a task as defined by its ID and, optionally, also downstream tasks in a given DagRun .
    """
    session.flush()
    subdag = task_dag.partial_subset(
        task_ids_or_regex={task_id},
        include_downstream=include_downstream,
        include_upstream=False,
    )
    subdag.clear(
        start_date=dag_run.execution_date,
        end_date=dag_run.execution_date,
        include_subdags=True,
        include_parentdag=True,
        only_failed=False,
        session=session,
    )


def _get_task_of_same_subject_by_short_id(
    base_task: TaskInstance, other_task_short_name: str
) -> str:
    this_id = base_task.task_id
    id_prefix = this_id.rsplit(".", maxsplit=1)[0]

    other_task_id = ".".join([id_prefix, other_task_short_name])
    return other_task_id


def _clear_task_from_same_subject(
    base_task: TaskInstance,
    other_task_short_name: str,
    dag_run: DagRun,
    dag: DAG,
    include_downstream: bool,
):

    first_id_to_reset = _get_task_of_same_subject_by_short_id(
        base_task, other_task_short_name
    )
    _clear_task(
        task_id=first_id_to_reset,
        dag_run=dag_run,
        task_dag=dag,
        include_downstream=include_downstream,
    )


def _make_manual_stages(subject_subdir):
    """
    Manual validation is more complex, as it involves validating both the tumor segmentation and the brain mask.
    If the brain mask is changed, the pipeline must go back to the brain_extract stage.
    We must also wait for the segmentation files to be approved in non-blocking way (so other tasks can still run)
    This is achieved with the architecture

    FileSensor -Failure--> Check Brain Mask Changed --Sucess (Changed)--> Back to brain extract (via HTTP to API)
                \                                   \--Failure(Unchanged) --> Back to FileSensor (via HTTP to API)
                 \
                  --Success-> Run rest of pipeline
    """
    AIRFLOW_DATA_DIR = os.getenv("AIRFLOW_DATA_DIR")
    ANNOTATED_FILE_NAME = (
        f"{'_'.join(subject_subdir.split(os.sep))}_tumorMask_model_0.nii.gz"
    )
    TUMOR_MASKS_DIR = os.path.join(
        AIRFLOW_DATA_DIR,
        "tumor_extracted",
        "DataForQC",
        subject_subdir,
        "TumorMasksForQC",
    )
    CONFIRMED_ANNOTATION_FILE = os.path.join(
        TUMOR_MASKS_DIR,
        "finalized",
        ANNOTATED_FILE_NAME,
    )
    BRAIN_MASK_CHANGED_FILE = os.path.join(TUMOR_MASKS_DIR, "tumor_mask_changed.json")

    @task(
        task_id=RANOTaskIDs.VALIDATE_SEGMENTATIONS_STATE,
        trigger_rule=TriggerRule.ALL_FAILED,
        task_display_name="Validate Upstream State",
    )
    def validate_segmentations_state(
        dag_run: DagRun = None, task_instance: TaskInstance = None
    ):
        upstream_segmentations_validated_id = _get_task_of_same_subject_by_short_id(
            task_instance, RANOTaskIDs.SEGMENTATIONS_VALIDATED
        )
        upstream_segmentations_validated_task = dag_run.get_task_instance(
            task_id=upstream_segmentations_validated_id
        )

        if upstream_segmentations_validated_task.state == State.FAILED:
            return
        raise AirflowSkipException(
            "Do not continue unless upstream state is explicitly Failed!"
        )

    segmentations_validated = FileSensor(
        filepath=CONFIRMED_ANNOTATION_FILE,  # TODO can also send directory to return True for any files there. Maybe this is better?
        task_id=RANOTaskIDs.SEGMENTATIONS_VALIDATED,
        task_display_name="Segmentations Validate",
        mode="reschedule",
        doc_md="Please run the RANO Monitoring tool to validate the existing segmentations or make manual corrections. "
        "This task will be successful once the finalized file is in the proper directory.",
        timeout=1,
        fs_conn_id="local_fs",
        poke_interval=20,
    )

    check_brain_mask_changed_stage = RANOStage(
        "manual_annotation",
        "--subject-subdir",
        subject_subdir,
        task_id=RANOTaskIDs.CHECK_BRAIN_MASK,
        task_display_name="Check Brain Mask",
    )
    check_brain_mask_changed = docker_operator_factory(check_brain_mask_changed_stage)

    @task.branch(
        task_id=RANOTaskIDs.BRAIN_MASK_CHANGED_BRANCH,
        task_display_name="Brain Mask Changed?",
    )
    def brain_mask_changed(task_instance: TaskInstance = None):
        if not os.path.exists(BRAIN_MASK_CHANGED_FILE):
            brain_mask_changed = False

        else:
            with open(BRAIN_MASK_CHANGED_FILE, "r") as f:
                brain_mask_changed = json.load(f)

        if brain_mask_changed:
            next_task_id = _get_task_of_same_subject_by_short_id(
                task_instance, RANOTaskIDs.CLEAR_RETURN_TO_BRAIN_EXTRACT
            )
        else:
            next_task_id = _get_task_of_same_subject_by_short_id(
                task_instance, RANOTaskIDs.CLEAR_RETURN_TO_SEGMENTATIONS_VALIDATED
            )

        return [next_task_id]

    @task(
        task_id=RANOTaskIDs.CLEAR_RETURN_TO_BRAIN_EXTRACT,
        task_display_name="Clear Downstream",
    )
    def clear_return_to_brain_extract(
        dag_run: DagRun = None,
        dag: DAG = None,
        task_instance: TaskInstance = None,
    ):
        _clear_task_from_same_subject(
            base_task=task_instance,
            other_task_short_name=RANOTaskIDs.RETURN_TO_BRAIN_EXTRACT,
            dag_run=dag_run,
            dag=dag,
            include_downstream=False,
        )

    @task(
        task_id=RANOTaskIDs.RETURN_TO_BRAIN_EXTRACT,
        task_display_name="Return to Brain Extraction",
    )
    def return_to_brain_extract(
        dag_run: DagRun = None,
        dag: DAG = None,
        task_instance: TaskInstance = None,
    ):
        _clear_task_from_same_subject(
            base_task=task_instance,
            other_task_short_name=RANOTaskIDs.EXTRACT_BRAIN,
            dag_run=dag_run,
            dag=dag,
            include_downstream=True,
        )

    @task(
        task_id=RANOTaskIDs.CLEAR_RETURN_TO_SEGMENTATIONS_VALIDATED,
        task_display_name="Clear Downstream",
    )
    def clear_return_to_file_sensor(
        dag_run: DagRun = None,
        dag: DAG = None,
        task_instance: TaskInstance = None,
    ):
        _clear_task_from_same_subject(
            base_task=task_instance,
            other_task_short_name=RANOTaskIDs.RETURN_TO_SEGMENTATIONS_VALIDATED,
            dag_run=dag_run,
            dag=dag,
            include_downstream=False,
        )

    @task(
        task_id=RANOTaskIDs.RETURN_TO_SEGMENTATIONS_VALIDATED,
        task_display_name="Return to Segmentatins Validate",
    )
    def return_to_file_sensor(
        dag_run: DagRun = None,
        dag: DAG = None,
        task_instance: TaskInstance = None,
    ):
        _clear_task_from_same_subject(
            base_task=task_instance,
            other_task_short_name=RANOTaskIDs.SEGMENTATIONS_VALIDATED,
            dag_run=dag_run,
            dag=dag,
            include_downstream=True,
        )

    brain_mask_changed_instance = brain_mask_changed()
    (
        segmentations_validated
        >> Label("NOT reviewed")
        >> validate_segmentations_state()
        >> check_brain_mask_changed
        >> brain_mask_changed_instance
    )
    (
        brain_mask_changed_instance
        >> Label("Yes")
        >> clear_return_to_brain_extract()
        >> return_to_brain_extract()
    )
    (
        brain_mask_changed_instance
        >> Label("No")
        >> clear_return_to_file_sensor()
        >> return_to_file_sensor()
    )

    return segmentations_validated


def make_pipeline_for_subject(subject_subdir):

    AUTO_STAGES = [
        RANOStage(
            "make_csv",
            "--subject-subdir",
            subject_subdir,
            task_display_name="Make CSV",
            task_id=RANOTaskIDs.MAKE_CSV,
        ),
        RANOStage(
            "convert_nifti",
            "--subject-subdir",
            subject_subdir,
            task_display_name="Convert to NIfTI",
            task_id=RANOTaskIDs.CONVERT_NIFTI,
        ),
        RANOStage(
            "extract_brain",
            "--subject-subdir",
            subject_subdir,
            task_display_name="Extract Brain",
            task_id=RANOTaskIDs.EXTRACT_BRAIN,
        ),
        RANOStage(
            "extract_tumor" "--subject-subdir",
            subject_subdir,
            task_display_name="Extract Tumor",
            task_id=RANOTaskIDs.EXTRACT_TUMOR,
        ),
    ]

    prev_task = None
    for stage in AUTO_STAGES:
        curr_task = docker_operator_factory(stage)
        if prev_task is not None:
            prev_task >> curr_task
        prev_task = curr_task

    segmentation_validation = _make_manual_stages(subject_subdir)
    if prev_task is not None:
        prev_task >> segmentation_validation

    segment_comparison_stage = RANOStage(
        "segmentation_comparison",
        "--subject-subdir",
        subject_subdir,
        task_display_name="Segment Comparison",
        task_id=RANOTaskIDs.SEGMENT_COMPARISON,
    )
    segment_comparison = docker_operator_factory(segment_comparison_stage)

    segmentation_validation >> Label("Reviwed") >> segment_comparison


def create_legal_id(subject_slash_timepoint, restrictive=False):
    import re

    if restrictive:
        legal_chars = "A-Za-z0-9_-"
    else:
        legal_chars = "A-Za-z0-9_.~:+-"
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
