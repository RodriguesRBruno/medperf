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
    SUBJECT_NIFTI_DATASETS,
    SUBJECT_TIMEPOINT_LIST,
    SUBJECT_TUMOR_EXTRACT_DATASETS,
    SUBJECT_DONE_DATASETS,
)
import os
from airflow.operators.empty import EmptyOperator
from airflow.utils.trigger_rule import TriggerRule
from airflow.sensors.filesystem import FileSensor
from airflow.utils.edgemodifier import Label

AIRFLOW_DATA_DIR = os.getenv("AIRFLOW_DATA_DIR")


for subject_slash_timepoint in SUBJECT_TIMEPOINT_LIST:
    inlet_dataset = SUBJECT_TUMOR_EXTRACT_DATASETS[subject_slash_timepoint]
    nifti_dataset = SUBJECT_NIFTI_DATASETS[
        subject_slash_timepoint
    ]  # Used to rollback to brain extraction
    outlet_dataset = SUBJECT_DONE_DATASETS[subject_slash_timepoint]

    dag_id = f"manual_{create_legal_id(subject_slash_timepoint)}"

    ANNOTATED_FILE_NAME = (
        f"{'_'.join(subject_slash_timepoint.split(os.sep))}_tumorMask_model_0.nii.gz"
    )

    BASE_REVIEW_DIR = os.path.join(
        AIRFLOW_DATA_DIR,
        "manual_review",
        subject_slash_timepoint,
    )

    CONFIRMED_TUMOR_EXTRACTION_FILE = os.path.join(
        BASE_REVIEW_DIR, "tumor_extraction", "finalized", ANNOTATED_FILE_NAME
    )

    CORRECTED_BRAIN_MASK_FILE = os.path.join(
        BASE_REVIEW_DIR,
        "brain_mask",
        "finalized",
        "brainMask_fused.nii.gz",
    )

    dag_doc = f"""
    """

    manual_approval_doc = f"""
    """

    with DAG(
        dag_id=dag_id,
        dag_display_name=f"Manual Approval",
        max_active_runs=1,
        schedule=[inlet_dataset],
        start_date=YESTERDAY,
        is_paused_upon_creation=False,
        tags=[subject_slash_timepoint, "Manual Approval"],
        doc_md=dag_doc,
    ) as dag:

        tumor_extraction_reviewed = FileSensor(
            filepath=CONFIRMED_TUMOR_EXTRACTION_FILE,
            task_id=rano_task_ids.TUMOR_EXTRACTION_REVIEW,
            task_display_name="Has Tumor Segmentation been reviewed?",
            doc_md="TODO",
            timeout=1,
            fs_conn_id="local_fs",
            poke_interval=20,
            max_wait=20,
        )

        segment_comparison_stage = RANOStage(
            "segmentation_comparison",
            "--subject-subdir",
            subject_slash_timepoint,
            task_display_name="Segment Comparison",
            task_id=rano_task_ids.SEGMENT_COMPARISON,
            outlets=[outlet_dataset],
        )
        segment_comparison = ContainerOperatorFactory.get_operator(
            segment_comparison_stage
        )

        brain_mask_modified = FileSensor(
            filepath=CORRECTED_BRAIN_MASK_FILE,
            task_id=rano_task_ids.BRAIN_MASK_REVIEW,
            task_display_name="Has the Brain Mask been modified?",
            doc_md="TODO",
            timeout=1,
            fs_conn_id="local_fs",
            poke_interval=20,
            max_wait=20,
            trigger_rule=TriggerRule.ALL_FAILED,
        )

        rollback_stage = RANOStage(
            "rollback_to_brain_extract",
            "--subject-subdir",
            subject_slash_timepoint,
            task_id=rano_task_ids.CHECK_BRAIN_MASK,
            task_display_name="Check Brain Mask",
        )

        return_to_brain_extract = EmptyOperator(
            task_id=rano_task_ids.RETURN_TO_BRAIN_EXTRACT,
            task_display_name="Return to Brain Extraction",
            outlets=[
                nifti_dataset
            ],  # Go to Brain Extract (stage right after NIfTI) is brain mask changed
        )

        return_to_manual_approval = EmptyOperator(
            task_id=rano_task_ids.RETURN_TO_TUMOR_EXTRACTION_REVIEW,
            task_display_name="Return to Segmentations Validate",
            outlets=[inlet_dataset],  # Repeat this DAG until approved,
            trigger_rule=TriggerRule.ALL_FAILED,
        )
        tumor_extraction_reviewed >> Label("Reviewed") >> segment_comparison
        tumor_extraction_reviewed >> Label("NOT Reviewed") >> brain_mask_modified

        brain_mask_modified >> Label("Yes") >> return_to_brain_extract
        brain_mask_modified >> Label("No") >> return_to_manual_approval
