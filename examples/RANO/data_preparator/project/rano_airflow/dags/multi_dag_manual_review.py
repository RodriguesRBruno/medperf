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
from airflow.decorators import task
from airflow.utils.edgemodifier import Label
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
    TUMOR_MASKS_DIR = os.path.join(
        AIRFLOW_DATA_DIR,
        "tumor_extracted",
        "DataForQC",
        subject_slash_timepoint,
        "TumorMasksForQC",
    )
    CONFIRMED_ANNOTATION_FILE = os.path.join(
        TUMOR_MASKS_DIR,
        "finalized",
        ANNOTATED_FILE_NAME,
    )

    with DAG(
        dag_id=dag_id,
        dag_display_name=f"RANO Pipeline - Manual Approval for {subject_slash_timepoint}",
        max_active_runs=1,
        schedule=[inlet_dataset],
        start_date=YESTERDAY,
        is_paused_upon_creation=False,
    ) as dag:

        segmentations_validated = FileSensor(
            filepath=CONFIRMED_ANNOTATION_FILE,  # TODO can also send directory to return True for any files there. Maybe this is better?
            task_id=rano_task_ids.SEGMENTATIONS_VALIDATED,
            task_display_name="Segmentations Validate",
            # mode="reschedule",
            doc_md="Please run the RANO Monitoring tool to validate the existing segmentations or make manual corrections. "
            "This task will be successful once the finalized file is in the proper directory.",
            timeout=1,
            fs_conn_id="local_fs",
            poke_interval=20,
        )

        check_brain_mask_changed_stage = RANOStage(
            "manual_annotation",
            "--subject-subdir",
            subject_slash_timepoint,
            task_id=rano_task_ids.CHECK_BRAIN_MASK,
            task_display_name="Check Brain Mask",
            trigger_rule=TriggerRule.ALL_FAILED,
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

            if not os.path.exists(BRAIN_MASK_CHANGED_FILE):
                brain_mask_changed = False

            else:
                with open(BRAIN_MASK_CHANGED_FILE, "r") as f:
                    brain_mask_changed = json.load(f)

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
        # @task(
        #     task_id=rano_task_ids.RETURN_TO_BRAIN_EXTRACT,
        #     task_display_name="Return to Brain Extraction",
        # )
        # def return_to_brain_extract(
        #     dag_run: DagRun = None,
        #     dag: DAG = None,
        #     task_instance: TaskInstance = None,
        # ):
        #     _clear_task_from_same_subject(
        #         base_task=task_instance,
        #         other_task_short_name=rano_task_ids.EXTRACT_BRAIN,
        #         dag_run=dag_run,
        #         dag=dag,
        #         include_downstream=True,
        #     )

        # @task(
        # task_id=rano_task_ids.RETURN_TO_SEGMENTATIONS_VALIDATED,
        # task_display_name="Return to Segmentatins Validate",
        # )
        # def return_to_file_sensor(
        #     dag_run: DagRun = None,
        #     dag: DAG = None,
        #     task_instance: TaskInstance = None,
        # ):
        #     _clear_task_from_same_subject(
        #         base_task=task_instance,
        #         other_task_short_name=rano_task_ids.SEGMENTATIONS_VALIDATED,
        #         dag_run=dag_run,
        #         dag=dag,
        #         include_downstream=True,
        #     )

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

        segmentations_validated >> Label("Reviewed") >> segment_comparison

        brain_mask_changed_instance = brain_mask_changed()
        (
            segmentations_validated
            >> Label("NOT reviewed")
            >> check_brain_mask_changed
            >> brain_mask_changed_instance
        )
        brain_mask_changed_instance >> Label("Yes") >> return_to_brain_extract
        brain_mask_changed_instance >> Label("No") >> return_to_manual_approval
