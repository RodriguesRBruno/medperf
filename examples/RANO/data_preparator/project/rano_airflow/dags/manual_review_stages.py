"""
This DAG runs the Manual Approval step.
This DAG is triggered by the "Tumor" dataset, which is triggered once bBrain and Tumor Extraction Finishes.
The "Tumor" dataset can also be triggered by this DAG in case no changes are detected to the automatic Brain Mask
and the automatic Tumor Segmentation has not been approved yet. This DAG will run continuously scanning for either
a modified Brain Mask or an accepted Tumor Segmentation until either is found.
If the Brain Mask is modified, this DAG will trigger the "NIfTI" dataset, causing the pipelin to execute the Brain
and Tumor Extraction (that come AFTER NIfTI conversion) again with the new Brain Mask.
If the automatic Tumor Segmentation is accepted, or if a modified Tumor Segmentation is provided, the pipeline will
proceed to the Segmentation Comparison stage.
Please read the DAG documentation in the UI or in the provided instructions document for further instructions on
how to provide a finalized Tumor Segmentation and/or Brain Mask correction in a way that the pipeline can automatically detect.
"""

from __future__ import annotations
from airflow.models.dag import DAG

from utils.utils import YESTERDAY
from utils.container_factory import ContainerOperatorFactory
from utils.utils import (
    create_documentation_for_manual_steps,
    get_manual_review_directory,
)
from utils import rano_task_ids, dag_ids, dag_tags
from utils.subject_datasets import (
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

    dag_id = dag_ids.MANUAL_APPROVAL[subject_slash_timepoint]

    brain_mask_review_doc, tumor_segmentation_review_doc, dag_doc = (
        create_documentation_for_manual_steps(subject_slash_timepoint)
    )

    confirmed_tumor_segmentation_file = get_manual_review_directory(
        subject_slash_timepoint, "tumor_extraction", "finalized"
    )
    corrected_brain_mask_file = get_manual_review_directory(
        subject_slash_timepoint, "brain_mask", "finalized"
    )

    with DAG(
        dag_id=dag_id,
        dag_display_name=f"Manual Approval - {subject_slash_timepoint}",
        max_active_runs=1,
        schedule=[inlet_dataset],
        start_date=YESTERDAY,
        is_paused_upon_creation=False,
        tags=[subject_slash_timepoint, dag_tags.MANUAL_APPROVAL],
        doc_md=dag_doc,
    ) as dag:

        tumor_extraction_reviewed = FileSensor(
            filepath=confirmed_tumor_segmentation_file,
            task_id=rano_task_ids.TUMOR_EXTRACTION_REVIEW,
            task_display_name="Has Tumor Segmentation been reviewed?",
            doc_md=tumor_segmentation_review_doc,
            timeout=1,
            fs_conn_id="local_fs",
            poke_interval=20,
            max_wait=20,
        )

        segment_comparison_stage = ContainerOperatorFactory.get_operator(
            "segmentation_comparison",
            "--subject-subdir",
            subject_slash_timepoint,
            task_display_name="Segment Comparison",
            task_id=rano_task_ids.SEGMENT_COMPARISON,
            outlets=[outlet_dataset],
        )

        brain_mask_modified = FileSensor(
            filepath=corrected_brain_mask_file,
            task_id=rano_task_ids.BRAIN_MASK_REVIEW,
            task_display_name="Has the Brain Mask been modified?",
            doc_md=brain_mask_review_doc,
            timeout=1,
            fs_conn_id="local_fs",
            poke_interval=20,
            max_wait=20,
            trigger_rule=TriggerRule.ALL_FAILED,
        )

        return_to_brain_extract_stage = ContainerOperatorFactory.get_operator(
            "rollback_to_brain_extract",
            "--subject-subdir",
            subject_slash_timepoint,
            task_id=rano_task_ids.RETURN_TO_BRAIN_EXTRACT,
            task_display_name="Rollback to Brain Extraction",
            outlets=[nifti_dataset],
        )

        return_to_manual_approval_stage = EmptyOperator(
            task_id=rano_task_ids.RETURN_TO_TUMOR_EXTRACTION_REVIEW,
            task_display_name="Return to Tumor Segmentation Review",
            outlets=[
                inlet_dataset
            ],  # Repeat this DAG until approved or brain mask changes,
            trigger_rule=TriggerRule.ALL_FAILED,
        )
        tumor_extraction_reviewed >> Label("Reviewed") >> segment_comparison_stage
        tumor_extraction_reviewed >> Label("NOT Reviewed") >> brain_mask_modified

        brain_mask_modified >> Label("Yes") >> return_to_brain_extract_stage
        brain_mask_modified >> Label("No") >> return_to_manual_approval_stage
