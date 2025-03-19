from __future__ import annotations
from airflow.decorators import task_group
from airflow.models.dag import DAG
from airflow.operators.empty import EmptyOperator
from airflow.utils.task_group import TaskGroup
from utils import make_pipeline_for_subject, read_subject_directories, create_legal_id

_SUBJECT_SUBDIRS = read_subject_directories()

with DAG(
    dag_id="rano_pipeline_all_subjects",
    dag_display_name="RANO Pipeline - All Subjects",
    catchup=True,
    is_paused_upon_creation=False,
) as dag:

    start = EmptyOperator(task_id="start")
    end = EmptyOperator(task_id="some_dataset_stage")

    all_task_groups = []
    for subject_subdir in _SUBJECT_SUBDIRS:
        subject_id = create_legal_id(subject_subdir, restrictive=True)

        with TaskGroup(
            subject_id, tooltip=f"Tasks for Subject {subject_subdir}"
        ) as this_task_group:
            make_pipeline_for_subject(subject_subdir)

        start >> this_task_group >> end
