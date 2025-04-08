"""
This DAG runs the finalizing stages of the pipeline.
It includes calculating how many of the Tumor Segmentations have been modified by the user,
a manual confirmation step (which the user must manually set as SUCCESS in the Airflow UI),
consolidating data provided by the pipeline, a final sanity_check and metrics generation.
This DAG will only run once all Manual Approval DAGs (for each subject/timepoint) have
been completed.
"""

from __future__ import annotations
from airflow.models.dag import DAG
from airflow.decorators import task
from airflow.exceptions import AirflowException
from utils.utils import YESTERDAY
from utils.container_factory import ContainerOperatorFactory
from utils.subject_datasets import ALL_DONE_DATASETS
from utils import rano_task_ids, dag_ids, dag_tags
import os

DATA_DIR = os.getenv("AIRFLOW_DATA_DIR")
msg_file = os.path.join(DATA_DIR, "auxiliary_files", ".msg")

try:
    with open(msg_file, "r") as f:
        percent_change = f.read()

except OSError:
    percent_change = None

if percent_change:
    dag_msg = f"""We have identified {percent_change}% of cases have not been modified 
              with respect to the baseline segmentation. If this is correct, please mark
              the task **Manual Confirmation** as **SUCCESS** to proceed with the pipeline."""
    task_msg = f"""We have identified {percent_change}% of cases have not been modified 
               with respect to the baseline segmentation. If this is correct, please mark
               the this task as **SUCCESS** to proceed with the pipeline."""
else:
    dag_msg = """Please wait until the conclusion of the **Calculate Changed Voxels** task before interacting with this DAG."""
    task_msg = """Please wait until the conclusion of the **Calculate Changed Voxels** task before interacting with this task."""


with DAG(
    dag_id=dag_ids.FINISH,
    dag_display_name="Validation and Finish",
    catchup=True,
    max_active_runs=1,
    schedule=ALL_DONE_DATASETS,
    start_date=YESTERDAY,
    is_paused_upon_creation=False,
    doc_md=dag_msg,
    tags=[dag_tags.ALL_SUBJECTS, dag_tags.FINISH],
) as dag:

    calculate_changed_voxels = ContainerOperatorFactory.get_operator(
        "calculate_changed_voxels",
        task_display_name="Calculate Changed Voxels",
        task_id=rano_task_ids.CALCULATE_CHANGED_VOXELS,
    )

    @task(
        task_id=rano_task_ids.CONFIRMATION_STAGE,
        task_display_name="Manual Confirmation",
        doc_md=task_msg,
    )
    def manual_confirmation():
        raise AirflowException("This task must be approved manually!")

    move_labeled_files = ContainerOperatorFactory.get_operator(
        "move_labeled_files",
        task_display_name="Move Labeled Files",
        task_id=rano_task_ids.MOVE_LABELED_FILES,
    )

    consolidation = ContainerOperatorFactory.get_operator(
        "consolidation_stage",
        # "--keep-files",  # Uncomment this line to keep files in the /data directory after execution
        task_display_name="Consolidation Stage",
        task_id=rano_task_ids.CONSOLIDATION_STAGE,
    )

    sanity_check = ContainerOperatorFactory.get_operator(
        "sanity_check",
        task_display_name="Sanity Check",
        task_id=rano_task_ids.SANITY_CHECK,
    )
    metrics = ContainerOperatorFactory.get_operator(
        "metrics",
        task_display_name="Evaluate Metrics",
        task_id=rano_task_ids.METRICS,
    )
    (
        calculate_changed_voxels
        >> manual_confirmation()
        >> move_labeled_files
        >> consolidation
        >> sanity_check
        >> metrics
    )
