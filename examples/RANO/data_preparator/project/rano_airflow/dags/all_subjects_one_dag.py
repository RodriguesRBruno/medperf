from __future__ import annotations
from airflow.models.dag import DAG
from airflow.utils.task_group import TaskGroup
from airflow.utils.trigger_rule import TriggerRule
from utils import (
    make_pipeline_for_subject,
    read_subject_directories,
    create_legal_id,
    dummy_operator_factory,
    docker_operator_factory,
)
from datetime import datetime

_SUBJECT_SUBDIRS = read_subject_directories()

with DAG(
    dag_id="rano_pipeline_all_subjects",
    dag_display_name="RANO Pipeline - All Subjects",
    catchup=True,
    max_active_runs=1,
    schedule="@once",
    start_date=datetime(2024, 1, 1),
    is_paused_upon_creation=True,
) as dag:

    with TaskGroup(
        group_id="finalizing_dataset_stages",
        tooltip="Final processing stages",
        default_args={"trigger_rule": TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS},
    ) as dataset_stages:

        confirmation = dummy_operator_factory(
            dummy_id="confirmation_stage", dummy_display_name="DUMMY Confirmation"
        )

        consolidation = docker_operator_factory(
            "consolidation_stage",
            task_display_name="Consolidation Stage",
        )

        confirmation >> consolidation

    with TaskGroup(
        group_id="Processing_All_Subjects",
        tooltip="Processing tasks for all subjects",
    ) as all_subjects_group:
        for subject_subdir in _SUBJECT_SUBDIRS:
            subject_id = create_legal_id(subject_subdir, restrictive=True)

            with TaskGroup(
                subject_id, tooltip=f"Tasks for Subject {subject_subdir}"
            ) as this_task_group:
                make_pipeline_for_subject(subject_subdir)

            this_task_group >> dataset_stages
