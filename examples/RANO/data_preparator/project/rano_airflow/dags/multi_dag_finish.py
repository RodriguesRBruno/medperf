from __future__ import annotations
from airflow.models.dag import DAG
from container_factory import ContainerOperatorFactory
from rano_stage import RANOStage
from datetime import timedelta
import rano_task_ids
from subject_datasets import YESTERDAY, ALL_DONE_DATASETS

with DAG(
    dag_id="rano_end",
    dag_display_name="Validation and Finish",
    catchup=True,
    max_active_runs=1,
    schedule=ALL_DONE_DATASETS,
    start_date=YESTERDAY,
    is_paused_upon_creation=False,
) as dag:

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
