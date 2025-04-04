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
from airflow.exceptions import AirflowException
from airflow.decorators import task
from airflow.utils.edgemodifier import Label
import time
import json

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
        "your/workspace/directory",  # TODO read this on initialization to print the proper path?
        AIRFLOW_DATA_DIR,
        "tumor_extracted",
        "DataForQC",
        subject_slash_timepoint,
    )

    TUMOR_EXTRACTED_FILE = os.path.join("TumorMasksForQC", ANNOTATED_FILE_NAME)

    BRAIN_MASK_FILE = os.path.join(
        BASE_REVIEW_DIR,
        "brainMask_fused.nii.gz",
    )

    dag_doc = f"""
    The first task on this DAG (named **Manual Approval**) must be manually set as either Success or Failure.
    Please review the Brain Mask for this subject located at {BRAIN_MASK_FILE} and the automatic Tumor Segmentation located at {TUMOR_EXTRACTED_FILE}.

    ## Reviewing the Brain Mask File.
    If the brain mask must be adjusted, please make the necessary corrections on the existing file located at {BRAIN_MASK_FILE} with the tool of your choice.
    **Do not change the file name or its location when  correcting it** 
    
    Note that this will cause the pipeline to re-execute the Brain Extraction and Tumor Extraction stages after a short wait period. 
    The final tumor extraction will need to be manually approved once ready.

    ## Reviewing the Tumor Segmentation
    If the brain mask does not need adjustments, or adjusments were made previously, please review the automatic Tumor Segmentation 
    located at {TUMOR_EXTRACTED_FILE}. 
    
    If necessary, please make the necessary corrections on the existing file located at {TUMOR_EXTRACTED_FILE} with the tool of your choice.
    **Do not change the file name or its location when  correcting it**.

    Once the manual corrections are made, or if manual corrections were not necessary, please set the **Manual Approval** task as **SUCCESS** manually.
    **Do *NOT* set any of the Upstream, Downstream, Past or Future options when setting the task as successful**. 
    Once the **Manual Approval** task is marked as successful, the pipeline will continue into its next stages. 
    The pipeline will only be finalized once all subjects are approved.
    """

    manual_approval_doc = f"""
    This task must be manually set as either Success or Failure.
    Please review the Brain Mask for this subject located at {BRAIN_MASK_FILE} and the automatic Tumor Segmentation located at {TUMOR_EXTRACTED_FILE}.

    ## Reviewing the Brain Mask File.
    If the brain mask must be adjusted, please make the necessary corrections on the existing file located at {BRAIN_MASK_FILE} with the tool of your choice.
    **Do not change the file name or its location when  correcting it** 
    
    Note that this will cause the pipeline to re-execute the Brain Extraction and Tumor Extraction stages after a short wait period. 
    The final tumor extraction will need to be manually approved once ready.

    ## Reviewing the Tumor Segmentation
    If the brain mask does not need adjustments, or adjusments were made previously, please review the automatic Tumor Segmentation 
    located at {TUMOR_EXTRACTED_FILE}. 
    
    If necessary, please make the necessary corrections on the existing file located at {TUMOR_EXTRACTED_FILE} with the tool of your choice.
    **Do not change the file name or its location when  correcting it**

    Once the manual corrections are made, or if manual corrections were not necessary, please set this task as **SUCCESS**. Once this task
    is marked as successfull, cause the pipeline will continue into its next stages. The pipeline will only be finalized once all subjects are approved.
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

        @task(
            doc_md=manual_approval_doc,
            task_display_name="Manual Approval",
            task_id=rano_task_ids.MANUAL_APPROVAL,
        )
        def manual_approval():
            time.sleep(60)
            raise AirflowException(
                f"This task must be set as Success manually by the user. Read the Task Documentation or the DAG documentation for further information."
            )

        check_brain_mask_changed_stage = RANOStage(
            "manual_annotation",
            "--subject-subdir",
            subject_slash_timepoint,
            task_id=rano_task_ids.CHECK_BRAIN_MASK,
            task_display_name="Check Brain Mask",
            trigger_rule=TriggerRule.ONE_FAILED,
        )
        check_brain_mask_changed = ContainerOperatorFactory.get_operator(
            check_brain_mask_changed_stage
        )

        @task.branch(
            task_id=rano_task_ids.BRAIN_MASK_CHANGED_BRANCH,
            task_display_name="Brain Mask Changed?",
        )
        def brain_mask_changed():
            BRAIN_MASK_CHANGED_FILE = os.path.join(
                AIRFLOW_DATA_DIR,
                "auxiliary_files",
                subject_slash_timepoint,
                "brain_mask_changed.json",
            )

            try:
                with open(BRAIN_MASK_CHANGED_FILE, "r") as f:
                    brain_mask_changed = json.load(f)
            except OSError:
                brain_mask_changed = False

            if brain_mask_changed:
                next_task_id = rano_task_ids.RETURN_TO_BRAIN_EXTRACT
            else:
                next_task_id = rano_task_ids.RETURN_TO_SEGMENTATIONS_VALIDATED

            return [next_task_id]

        return_to_brain_extract = EmptyOperator(
            task_id=rano_task_ids.RETURN_TO_BRAIN_EXTRACT,
            task_display_name="Return to Brain Extraction",
            outlets=[
                nifti_dataset
            ],  # Go to Brain Extract (stage right after NIfTI) is brain mask changed
        )

        return_to_manual_approval = EmptyOperator(
            task_id=rano_task_ids.RETURN_TO_SEGMENTATIONS_VALIDATED,
            task_display_name="Return to Segmentations Validate",
            outlets=[inlet_dataset],  # Repeat this DAG until approved
        )

        segment_comparison_stage = RANOStage(
            "segmentation_comparison",
            "--subject-subdir",
            subject_slash_timepoint,
            task_display_name="Segment Comparison",
            task_id=rano_task_ids.SEGMENT_COMPARISON,
            outlets=[outlet_dataset],
            trigger_rule=TriggerRule.NONE_FAILED_OR_SKIPPED,
        )
        segment_comparison = ContainerOperatorFactory.get_operator(
            segment_comparison_stage
        )

        manual_approval_instance = manual_approval()
        brain_mask_changed_instance = brain_mask_changed()
        manual_approval_instance >> Label("Reviewed") >> segment_comparison

        (
            manual_approval_instance
            >> Label("NOT reviewed")
            >> check_brain_mask_changed
            >> brain_mask_changed_instance
        )
        brain_mask_changed_instance >> Label("Yes") >> return_to_brain_extract
        brain_mask_changed_instance >> Label("No") >> return_to_manual_approval
