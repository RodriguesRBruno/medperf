"""
This DAG runs the Brain and Tumor Extraction stages.
This DAG is triggered by the "NIfTI dataset, which is triggered once NIfTI conversion finishes.
The "NIfTI" dataset can also be triggered in the Manual Review DAG in case the Brain Mask is modified.
In this situation, this DAG (Brain and Tumor Extraction) will run again using the new Brain Mask.
Once finished, this DAG writes to the Tumor dataset, which signals that Manual Review can proceed.
"""

from __future__ import annotations
from airflow.models.dag import DAG

from utils.utils import YESTERDAY
from utils.container_factory import ContainerOperatorFactory
from utils import rano_task_ids, dag_ids, dag_tags
from utils.subject_datasets import (
    SUBJECT_TIMEPOINT_LIST,
    SUBJECT_NIFTI_DATASETS,
    SUBJECT_TUMOR_EXTRACT_DATASETS,
)
from utils.pools import EXTRACTION_POOL


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

        brain_extraction_stage = ContainerOperatorFactory.get_operator(
            "extract_brain",
            "--subject-subdir",
            subject_slash_timepoint,
            task_display_name="Extract Brain",
            task_id=rano_task_ids.EXTRACT_BRAIN,
            pool=EXTRACTION_POOL.pool,
            pool_slots=3,
        )
        tumor_extraction_stage = ContainerOperatorFactory.get_operator(
            "extract_tumor",
            "--subject-subdir",
            subject_slash_timepoint,
            task_display_name="Extract Tumor",
            task_id=rano_task_ids.EXTRACT_TUMOR,
            pool=EXTRACTION_POOL.pool,
        )
        prepare_for_manual_review_stage = ContainerOperatorFactory.get_operator(
            "prepare_for_manual_review",
            "--subject-subdir",
            subject_slash_timepoint,
            task_display_name="Prepare for Manual Review",
            task_id=rano_task_ids.PREPARE_FOR_MANUAL_REVIEW,
            outlets=[outlet_dataset],
        )

        (
            brain_extraction_stage
            >> tumor_extraction_stage
            >> prepare_for_manual_review_stage
        )
