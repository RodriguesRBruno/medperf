from __future__ import annotations
from airflow.models.dag import DAG
from airflow.utils.task_group import TaskGroup
from airflow.utils.trigger_rule import TriggerRule
from container_factory import ContainerOperatorFactory
from rano_stage import RANOStage
from utils import (
    make_pipeline_for_subject,
    read_subject_directories,
    create_legal_id,
)
from datetime import datetime, timedelta
import rano_task_ids

YESTERDAY = datetime.today() - timedelta(days=1)

_SUBJECT_SUBDIRS = read_subject_directories()

with DAG(
    dag_id="rano_pipeline",
    dag_display_name="RANO Pipeline - All Subjects",
    catchup=True,
    max_active_runs=1,
    schedule="@once",
    start_date=YESTERDAY,
    is_paused_upon_creation=False,
) as dag:

    with TaskGroup(group_id="report_creation_stage") as report_stage:
        report = ContainerOperatorFactory.get_operator(
            RANOStage(
                command="create_report",
                task_display_name="Create Report Stage",
                task_id=rano_task_ids.CREATE_REPORT,
            )
        )

    with TaskGroup(
        group_id="finalizing_dataset_stages",
        tooltip="Final processing stages",
        default_args={"trigger_rule": TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS},
    ) as finalizing_stages:

        confirmation = ContainerOperatorFactory.get_operator(
            RANOStage(
                command="confirmation_stage",
                task_display_name="Confirmation Stage",
                task_id=rano_task_ids.CONFIRMATION_STAGE,
            )
        )

        consolidation = ContainerOperatorFactory.get_operator(
            RANOStage(
                "consolidation_stage",
                task_display_name="Consolidation Stage",
                task_id=rano_task_ids.CONSOLIDATION_STAGE,
                retries=1000,
                retry_delay=timedelta(minutes=1),
                retry_exponential_backoff=True,
                max_retry_delay=timedelta(minutes=15),
            )
        )

        confirmation >> consolidation

    with TaskGroup(
        group_id="Subjects",
        tooltip="Processing tasks for all subjects",
    ) as all_subjects_group:
        for subject_id, timepoint_list in _SUBJECT_SUBDIRS.items():
            subject_task_group_id = create_legal_id(subject_id, restrictive=True)

            with TaskGroup(
                group_id=subject_task_group_id,
                tooltip=f"Tasks for Subject ID {subject_id}",
            ) as subject_task_group:
                for timepoint in timepoint_list:
                    timepoint_task_group_id = create_legal_id(
                        timepoint, restrictive=True
                    )

                    with TaskGroup(
                        timepoint_task_group_id,
                        tooltip=f"Tasks for Subject {subject_id}/{timepoint}",
                    ) as subject_timepoint_task_group:
                        make_pipeline_for_subject(subject_id, timepoint)

                    report_stage >> subject_timepoint_task_group >> finalizing_stages
