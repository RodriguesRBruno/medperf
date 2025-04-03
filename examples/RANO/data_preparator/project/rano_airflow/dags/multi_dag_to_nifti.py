from __future__ import annotations
from airflow.models.dag import DAG

from container_factory import ContainerOperatorFactory
from rano_stage import RANOStage
from utils import (
    create_legal_id,
)
import rano_task_ids
from subject_datasets import (
    YESTERDAY,
    REPORT_DATASET,
    SUBJECT_TIMEPOINT_LIST,
    SUBJECT_NIFTI_DATASETS,
)


for subject_slash_timepoint in SUBJECT_TIMEPOINT_LIST:
    outlet_dataset = SUBJECT_NIFTI_DATASETS[subject_slash_timepoint]

    dag_id = f"nifti_{create_legal_id(subject_slash_timepoint)}"
    with DAG(
        dag_id=dag_id,
        dag_display_name=f"NIfTI Conversion",
        max_active_runs=1,
        schedule=[REPORT_DATASET],
        start_date=YESTERDAY,
        is_paused_upon_creation=False,
        tags=[subject_slash_timepoint],
        doc_md="Converting DICOM images to NIfTI",
    ) as dag:

        AUTO_STAGES = [
            RANOStage(
                "make_csv",
                "--subject-subdir",
                subject_slash_timepoint,
                task_display_name="Make CSV",
                task_id=rano_task_ids.MAKE_CSV,
            ),
            RANOStage(
                "convert_nifti",
                "--subject-subdir",
                subject_slash_timepoint,
                task_display_name="Convert to NIfTI",
                task_id=rano_task_ids.CONVERT_NIFTI,
                outlets=[outlet_dataset],
            ),
        ]

        prev_task = None
        for stage in AUTO_STAGES:
            curr_task = ContainerOperatorFactory.get_operator(stage)
            if prev_task is not None:
                prev_task >> curr_task
            prev_task = curr_task
