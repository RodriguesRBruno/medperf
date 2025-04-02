from __future__ import annotations
from airflow.models.dag import DAG
from container_factory import ContainerOperatorFactory
from rano_stage import RANOStage
import rano_task_ids
from subject_datasets import YESTERDAY, REPORT_DATASET


with DAG(
    dag_id="rano_setup",
    dag_display_name="RANO Pipeline - Initial Setup",
    catchup=True,
    max_active_runs=1,
    schedule="@once",
    start_date=YESTERDAY,
    is_paused_upon_creation=False,
) as dag:

    report = ContainerOperatorFactory.get_operator(
        RANOStage(
            command="create_report",
            task_display_name="Create Report Stage",
            task_id=rano_task_ids.CREATE_REPORT,
            outlets=[REPORT_DATASET],
        )
    )
