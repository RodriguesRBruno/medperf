from __future__ import annotations
from airflow.decorators import task_group
from airflow.models.dag import DAG
from airflow.models.param import Param


from utils import make_pipeline_for_subject


with DAG(
    dag_id="rano_pipeline",
    dag_display_name="RANO Pipeline",
    catchup=True,
    params={
        "subject_subdir": Param("XXXX/YYYY.MM.DD", type="string"),
    },
    is_paused_upon_creation=False,
) as dag:
    make_pipeline_for_subject("{{ params.subject_subdir}}")
