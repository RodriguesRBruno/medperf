from __future__ import annotations
import os
from airflow.decorators import task
from airflow.models.dag import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from datetime import datetime
from utils import create_legal_id, read_subject_directories

with DAG(
    dag_id=f"read_subject_ids",
    dag_display_name="Read Subject Data",
    catchup=True,
    max_active_runs=1,
    schedule="@once",
    start_date=datetime(2024, 1, 1),
    is_paused_upon_creation=False,
) as dag:

    @task
    def create_configs_for_subjects():
        subject_id_timepoint_directories = read_subject_directories()
        expand_args = []
        for subject_id_timepoint in subject_id_timepoint_directories:
            this_config = {
                "conf": {"subject_subdir": subject_id_timepoint},
                "trigger_run_id": create_legal_id(subject_id_timepoint),
            }
            expand_args.append(this_config)

        return expand_args

    subject_id_configs = create_configs_for_subjects()

    run_dags = TriggerDagRunOperator.partial(
        task_id="run_rano_pipeline", trigger_dag_id="rano_pipeline"
    ).expand_kwargs(subject_id_configs)
