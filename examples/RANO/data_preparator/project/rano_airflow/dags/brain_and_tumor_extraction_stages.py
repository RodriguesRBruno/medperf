from __future__ import annotations
from airflow.models.dag import DAG

from utils.container_factory import ContainerOperatorFactory
from utils.rano_stage import RANOStage
from utils import rano_task_ids, dag_ids, dag_tags
from utils.subject_datasets import (
    YESTERDAY,
    SUBJECT_TIMEPOINT_LIST,
    SUBJECT_NIFTI_DATASETS,
    SUBJECT_TUMOR_EXTRACT_DATASETS,
)
from datetime import timedelta


for subject_slash_timepoint in SUBJECT_TIMEPOINT_LIST:
    inlet_dataset = SUBJECT_NIFTI_DATASETS[subject_slash_timepoint]
    outlet_dataset = SUBJECT_TUMOR_EXTRACT_DATASETS[subject_slash_timepoint]

    dag_id = dag_ids.TUMOR_EXTRACTION[subject_slash_timepoint]
    with DAG(
        dag_id=dag_id,
        dag_display_name=f"Tumor Extraction - {subject_slash_timepoint}",
        max_active_runs=1,
        schedule=[inlet_dataset],
        start_date=YESTERDAY,
        is_paused_upon_creation=False,
        tags=[subject_slash_timepoint, dag_tags.TUMOR_EXTRACTION],
    ) as dag:

        AUTO_STAGES = [
            RANOStage(
                "extract_brain",
                "--subject-subdir",
                subject_slash_timepoint,
                task_display_name="Extract Brain",
                task_id=rano_task_ids.EXTRACT_BRAIN,
            ),
            RANOStage(
                "extract_tumor",
                "--subject-subdir",
                subject_slash_timepoint,
                task_display_name="Extract Tumor",
                task_id=rano_task_ids.EXTRACT_TUMOR,
                retries=1000,
                retry_delay=timedelta(minutes=15),
                retry_exponential_backoff=True,
                max_retry_delay=timedelta(hours=1),
            ),
            RANOStage(
                "prepare_for_manual_review",
                "--subject-subdir",
                subject_slash_timepoint,
                task_display_name="Prepare for Manual Review",
                task_id=rano_task_ids.PREPARE_FOR_MANUAL_REVIEW,
                outlets=[outlet_dataset],
            ),
        ]

        prev_task = None
        for stage in AUTO_STAGES:
            curr_task = ContainerOperatorFactory.get_operator(stage)
            if prev_task is not None:
                prev_task >> curr_task
            prev_task = curr_task
