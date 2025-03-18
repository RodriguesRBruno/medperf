from __future__ import annotations
import os
from airflow.decorators import task
from airflow.models.dag import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from datetime import datetime

INPUT_DATA_DIR = os.getenv("AIRFLOW_INPUT_DATA_DIR")

prev_task = curr_task = None

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
    def read_subject_directories():
        subject_id_timepoint_directories = []

        for subject_id_dir in os.listdir(INPUT_DATA_DIR):
            subject_complete_dir = os.path.join(INPUT_DATA_DIR, subject_id_dir)

            for timepoint_dir in os.listdir(subject_complete_dir):
                subject_id_timepoint_dir = os.path.join(subject_id_dir, timepoint_dir)
                subject_id_timepoint_directories.append(subject_id_timepoint_dir)

        as_conf = [
            {"subject_subdir": subdir} for subdir in subject_id_timepoint_directories
        ]
        print(f"{as_conf=}")
        return as_conf

    subject_id_dirs = read_subject_directories()

    run_dags = TriggerDagRunOperator.partial(
        task_id="run_rano_pipeline", trigger_dag_id="rano_pipeline"
    ).expand(
        conf=subject_id_dirs,
    )
