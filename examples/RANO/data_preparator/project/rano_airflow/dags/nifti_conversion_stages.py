"""
This DAG runs the NIfTI conversion step, as well as the required CSV creation before that.
This DAG is triggered by the "report" dataset, which is triggered once initial setup finishes.
Once finished, it writes to the NIfTI dataset, which signals that Brain Extraction can proceed.
"""

from __future__ import annotations
from airflow.models.dag import DAG

from utils.utils import YESTERDAY
from utils.container_factory import ContainerOperatorFactory
from utils import rano_task_ids, dag_ids, dag_tags
from utils.subject_datasets import (
    SETUP_DATASET,
    SUBJECT_TIMEPOINT_LIST,
    SUBJECT_NIFTI_DATASETS,
)
from utils.pools import NIFTI_POOL


for subject_slash_timepoint in SUBJECT_TIMEPOINT_LIST:
    outlet_dataset = SUBJECT_NIFTI_DATASETS[subject_slash_timepoint]

    dag_id = dag_ids.NIFTI_CONVERSION[subject_slash_timepoint]
    with DAG(
        dag_id=dag_id,
        dag_display_name=f"NIfTI Conversion - {subject_slash_timepoint}",
        max_active_runs=1,
        schedule=[SETUP_DATASET],
        start_date=YESTERDAY,
        is_paused_upon_creation=False,
        tags=[subject_slash_timepoint, dag_tags.NIFTI_CONVERSION],
        doc_md="Converting DICOM images to NIfTI",
    ) as dag:

        make_csv_stage = ContainerOperatorFactory.get_operator(
            "make_csv",
            "--subject-subdir",
            subject_slash_timepoint,
            task_display_name="Make CSV",
            task_id=rano_task_ids.MAKE_CSV,
        )
        convert_to_nifti_stage = ContainerOperatorFactory.get_operator(
            "convert_nifti",
            "--subject-subdir",
            subject_slash_timepoint,
            task_display_name="Convert to NIfTI",
            task_id=rano_task_ids.CONVERT_NIFTI,
            outlets=[outlet_dataset],
            pool=NIFTI_POOL.pool,
        )

        make_csv_stage >> convert_to_nifti_stage
