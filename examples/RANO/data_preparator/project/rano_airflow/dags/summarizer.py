"""
This DAG is responsible for summarizing the status of the pipeline into a
yaml file that can be sent to the MedPerf stage. This summary can be used
by the Benchmark Comitte to track how Data Preparation is going at each
participant and assist users that appear to be struggling.
"""

from __future__ import annotations
from airflow.decorators import task
from airflow.models.dag import DAG
from airflow.models.dagbag import DagBag
from airflow.models.dagrun import DagRun
from utils import dag_ids, dag_tags, rano_task_ids
from utils.utils import YESTERDAY
from utils.utils import ReportSummary
from datetime import timedelta
from airflow.utils.state import State


with DAG(
    dag_id=dag_ids.SUMMARIZER,
    dag_display_name="Summarizer",
    catchup=True,
    max_active_runs=1,
    schedule=timedelta(minutes=30),
    start_date=YESTERDAY,
    is_paused_upon_creation=False,
    doc_md="This DAG generates and periodically updates the report_summary.yaml file that is sent to the MedPerf servers.",
    tags=[dag_tags.SUMMARIZER],
) as dag:

    def _get_dags_and_subject_tags() -> tuple[dict[str, DAG], set[str]]:
        dag_bag: DagBag = DagBag(include_examples=False)
        relevant_dags: list[DAG] = [
            dag
            for dag in dag_bag.dags.values()
            if dag.tags and dag_tags.SUMMARIZER not in dag.tags
        ]

        subject_tags = set()
        for dag in relevant_dags:
            for tag in dag.tags:
                if tag not in dag_tags.DEFAULT_SUBJECT_TAGS:
                    subject_tags.add(tag)

        all_dags = {dag.dag_id: dag for dag in relevant_dags}
        all_dags = {
            dag_id: all_dags[dag_id]
            for dag_id in sorted(
                all_dags,
                key=lambda x: (
                    (
                        dag_tags.SETUP not in all_dags[x].tags,
                        dag_tags.NIFTI_CONVERSION not in all_dags[x].tags,
                        dag_tags.TUMOR_EXTRACTION not in all_dags[x].tags,
                        dag_tags.MANUAL_APPROVAL not in all_dags[x].tags,
                        dag_tags.FINISH not in all_dags[x].tags,
                    ),
                    all_dags[x].dag_id,
                ),
            )
        }

        return all_dags, subject_tags

    def _get_most_recent_dag_runs(all_dags: dict[str, DAG]) -> dict[str, DagRun | None]:
        setup_dag = all_dags[dag_ids.SETUP]
        last_setup_dag_run: DagRun = setup_dag.get_last_dagrun(
            include_externally_triggered=True
        )

        if last_setup_dag_run is None:
            most_recent_dag_runs: dict[str, DagRun | None] = {
                dag_id: None for dag_id in all_dags.keys()
            }
        else:
            most_recent_dag_runs: dict[str, DagRun | None] = {
                dag_id: dag.get_last_dagrun(include_externally_triggered=True)
                for dag_id, dag in all_dags.items()
            }
            # Filter older runs from before last setup
            most_recent_dag_runs = {
                dag_id: (
                    dag_run
                    if dag_run is None
                    or dag_run.execution_date >= last_setup_dag_run.execution_date
                    else None
                )
                for dag_id, dag_run in most_recent_dag_runs.items()
            }

        return most_recent_dag_runs

    def _get_report_summary(
        all_dags: dict[str, DAG],
        subject_tags: set[str],
        most_recent_dag_runs: dict[str, DagRun | None],
    ):
        import pandas as pd  # Import in task to not slow down dag parsing

        progress_df = pd.DataFrame(
            {
                "SubjectID": [],  # Including timepoint
                "DAG Tag": [],
                "Task Name": [],  # Does not include Subject Tag
                "Task Status": [],
            }
        )

        for dag_id, run_obj in most_recent_dag_runs.items():
            subject_id = "All"  # Default for Setup/Finish DAGs
            dag_tag = None
            corresponding_dag = all_dags[dag_id]
            for tag in corresponding_dag.tags:
                if tag in subject_tags:
                    subject_id = tag
                else:
                    dag_tag = tag

            if dag_tag == dag_tags.MANUAL_APPROVAL:
                # Report whole manual approve DAG as just one thing; no need to go into detail
                state = run_obj.state if run_obj else State.NONE
                update_dict = {
                    "Task Name": "Manual Approval Stage",
                    "DAG Tag": dag_tag,
                    "Task Status": state,
                    "SubjectID": subject_id,
                }
                task_df = pd.DataFrame([update_dict])
                progress_df = pd.concat([progress_df, task_df])
            else:
                if run_obj is None:
                    task_list = all_dags[dag_id].tasks
                    for task in task_list:
                        task.state = State.NONE
                else:
                    task_list = run_obj.get_task_instances()

                for task in task_list:
                    update_dict = {
                        "Task Name": task.task_display_name,
                        "DAG Tag": dag_tag,
                        "Task Status": task.state,
                        "SubjectID": subject_id,
                    }
                    task_df = pd.DataFrame([update_dict])
                    progress_df = pd.concat([progress_df, task_df])

        all_tasks = progress_df["Task Name"].unique()
        summary_dict = {
            dag_tags.SETUP: {},
            dag_tags.NIFTI_CONVERSION: {},
            dag_tags.TUMOR_EXTRACTION: {},
            dag_tags.MANUAL_APPROVAL: {},
            dag_tags.FINISH: {},
        }

        for task_name in all_tasks:
            relevant_df = progress_df[progress_df["Task Name"] == task_name]
            success_ratio = len(
                relevant_df[relevant_df["Task Status"] == State.SUCCESS]
            ) / len(relevant_df)
            sucess_percentage = round(success_ratio * 100, 3)
            dag_tag_list = relevant_df["DAG Tag"].unique()
            for dag_tag in dag_tag_list:
                summary_dict[dag_tag][task_name] = sucess_percentage

        for dag_tag, task_progress_dict in summary_dict.items():
            task_progress_dict = {
                key: task_progress_dict[key]
                for key in sorted(
                    task_progress_dict, key=lambda x: task_progress_dict[x]
                )
            }

        execution_status = "done"
        for dag_id, task_dict in summary_dict.items():
            for task_name, completion in task_dict.items():
                if completion < 100.0:
                    execution_status = "running"
                    break

        report_summary = ReportSummary(
            execution_status=execution_status, progress_dict=summary_dict
        )
        return report_summary

    @task(task_id=rano_task_ids.SUMMARIZER, task_display_name="Pipeline Summarizer")
    def rano_summarizer():

        all_dags, subject_tags = _get_dags_and_subject_tags()
        most_recent_dag_runs = _get_most_recent_dag_runs(all_dags)
        report_summary = _get_report_summary(
            all_dags, subject_tags, most_recent_dag_runs
        )
        report_summary.write_yaml()

    rano_summarizer()
