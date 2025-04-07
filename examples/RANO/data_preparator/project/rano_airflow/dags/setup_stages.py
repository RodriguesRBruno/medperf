from __future__ import annotations
from airflow.models.dag import DAG
from utils.container_factory import ContainerOperatorFactory
from utils.rano_stage import RANOStage
from utils import rano_task_ids, dag_ids, dag_tags
from utils.subject_datasets import YESTERDAY, REPORT_DATASET


with DAG(
    dag_id=dag_ids.SETUP,
    dag_display_name="Initial Setup",
    catchup=True,
    max_active_runs=1,
    schedule="@once",
    start_date=YESTERDAY,
    is_paused_upon_creation=False,
    doc_md="Initial setup creating necessary directories",
    tags=[dag_tags.ALL_SUBJECTS, dag_tags.SETUP],
) as dag:

    report = ContainerOperatorFactory.get_operator(
        RANOStage(
            command="create_report",
            task_display_name="Create Report Stage",
            task_id=rano_task_ids.CREATE_REPORT,
            outlets=[REPORT_DATASET],
        )
    )
