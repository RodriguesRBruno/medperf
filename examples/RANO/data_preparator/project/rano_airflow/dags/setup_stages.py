"""
This DAG is responsible for the initial setup of the Pipeline.
It is the only one of the pipeline DAGs set up to run immediately as soon as Airflow is started.
The other Pipeline DAGs (located in nifti_conversion_stages.py, brain_and_tumor_extraction_stages.py,
manual_review_stages.py and finishing_stages.py) are triggered to run using Airflow's Datasets feature,
which allows for data-aware scheduling. That is, the following DAGs will only run once the previous required
stages have been executed.
"""

from __future__ import annotations
from airflow.models.dag import DAG
from utils.utils import YESTERDAY
from utils.container_factory import ContainerOperatorFactory
from utils import rano_task_ids, dag_ids, dag_tags
from utils.subject_datasets import SETUP_DATASET


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
        "initial_setup",
        task_display_name="Initial Setup Stage",
        task_id=rano_task_ids.INITIAL_SETUP,
        outlets=[SETUP_DATASET],
    )
