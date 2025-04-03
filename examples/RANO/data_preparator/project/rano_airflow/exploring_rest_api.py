# REST API docs: https://airflow.apache.org/docs/apache-airflow/2.10.5/stable-rest-api-ref.html#section/Overview
import time

start = time.perf_counter()


import os
from dotenv import load_dotenv
from airflow_client import (
    client,
)  # TODO add this to requirements wherever this ends up (scripts/monitor? medperf itself? to be seen)
from airflow_client.client.api import dag_api, dag_run_api, task_instance_api
from airflow.utils.state import State
from airflow_client.client.model.dag_collection import DAGCollection
from collections import defaultdict

State.PENDING = "pending"

load_dotenv()

configuration = client.Configuration(
    host="http://localhost:8080/api/v1",
    username=os.getenv("AIRFLOW_USER"),
    password=os.getenv("AIRFLOW_PASS"),
)

dag_id = "rano_pipeline"


def wrapped_api_call(api_function: callable, *args, return_only_dict=True, **kwargs):
    try:
        raw_result = api_function(*args, **kwargs)
        if return_only_dict:
            return raw_result.to_dict()
        else:
            return raw_result
    except client.ApiException as e:
        print(f"Exception when calling {api_function.__name__}: {e}")


def sort_dag_or_task_list(dag_or_task_list):
    try:
        sorted_list = sorted(
            dag_or_task_list,
            key=lambda x: (
                x["state"] == State.FAILED,
                x["state"] == State.RUNNING,
                x["state"] == State.QUEUED,
                x["state"] == None,
                x["state"] != State.SUCCESS,
                (
                    x["end_date"]
                    if "end_date" in x and x["end_date"] is not None
                    else "ZZZZZZ"
                ),
                (
                    x["execution_date"]
                    if "execution_date" in x and x["execution_date"] is not None
                    else "ZZZZZZ"
                ),
            ),
            reverse=True,
        )
    except TypeError:
        print("Error sorting this list!")
        print(dag_or_task_list)
        raise
    return sorted_list


def _get_tag_to_dags_dict(
    dags_raw_result: DAGCollection, include_untagged: bool = False
) -> dict[str, list[dict[str, str]]]:
    tag_to_dag_dict = defaultdict(lambda: list())
    for dag in dags_raw_result["dags"]:
        if not dag["tags"] and include_untagged:
            tag_to_dag_dict["Untagged"].append(dag)
            continue

        for tag in dag["tags"]:
            tag_name = tag["name"]
            tag_to_dag_dict[tag_name].append(dag)
    return tag_to_dag_dict


with client.ApiClient(configuration, pool_threads=50) as api_client:

    dag_api_instance = dag_api.DAGApi(api_client)
    dag_run_api_instance = dag_run_api.DAGRunApi(api_client)

    dags = wrapped_api_call(
        dag_api_instance.get_dags,
        only_active=True,
        fields=["dag_id", "tags"],
    )

    tag_to_dags_dict = _get_tag_to_dags_dict(dags)
    sorted_tags = sorted(
        tag_to_dags_dict,
        key=lambda x: (x == "Untagged", "Finish" in x, "Setup" not in x),
    )
    tag_to_dags_dict = {
        sorted_key: tag_to_dags_dict[sorted_key] for sorted_key in sorted_tags
    }

    tag_to_dag_to_threads = {}
    # Initialize requests
    for tag, dag_list in tag_to_dags_dict.items():
        tag_to_dag_to_threads[tag] = {}
        for dag in dag_list:
            dag_id = dag["dag_id"]
            dag_details_thread = dag_api_instance.get_dag_details(
                dag_id=dag_id,
                async_req=True,
                fields=["dag_id", "dag_display_name", "doc_md"],
            )
            dag_runs_thread = dag_run_api_instance.get_dag_runs(
                dag_id=dag_id,
                order_by="-execution_date",  # Most recent first
                fields=[
                    "dag_id",
                    "dag_run_id",
                    "state",
                    "execution_date",
                    "end_date",
                ],  # TODO validate start/end times of dag run
                limit=1,
                async_req=True,
            )
            dag_task_definitions_thread = dag_api_instance.get_tasks(
                dag_id=dag_id, async_req=True
            )

            tag_to_dag_to_threads[tag][dag["dag_id"]] = {
                "details": dag_details_thread,
                "runs": dag_runs_thread,
                "tasks": dag_task_definitions_thread,
            }


dags_with_runs = []
tag_to_running_info = {tag: [] for tag in tag_to_dags_dict}
for tag, dag_dict in tag_to_dag_to_threads.items():
    for dag_id, dag_info_dict in dag_dict.items():
        base_dag_dict = dag_info_dict["details"].get().to_dict()
        dag_runs = dag_info_dict["runs"].get().to_dict()["dag_runs"]
        task_definitions = dag_info_dict["tasks"].get().to_dict()["tasks"]
        base_dag_dict["tasks"] = task_definitions

        if dag_runs:
            base_dag_dict["run"] = dag_runs[0]
            dags_with_runs.append(base_dag_dict)

        else:
            for dag_task in base_dag_dict["tasks"]:
                dag_task["state"] = State.PENDING

            base_dag_dict["state"] = State.PENDING

        tag_to_running_info[tag].append(base_dag_dict)

if dags_with_runs:
    with client.ApiClient(configuration, pool_threads=50) as api_client:
        task_instance_api_instance = task_instance_api.TaskInstanceApi(api_client)
        for dag in dags_with_runs:
            run_info = dag.pop("run")
            dag["state"] = run_info["state"]
            dag["task_instances_thread"] = (
                task_instance_api_instance.get_task_instances(
                    dag_id=dag["dag_id"],
                    dag_run_id=run_info["dag_run_id"],
                    async_req=True,
                )
            )

    for dag in dags_with_runs:
        task_instances = dag.pop("task_instances_thread").get().to_dict()
        task_instances = task_instances["task_instances"]
        task_definitions = dag.pop("tasks")
        task_id_to_doc_md = {
            task["task_id"]: task["doc_md"] for task in task_definitions
        }
        for task_instance in task_instances:
            task_instance["doc_md"] = task_id_to_doc_md[task_instance["task_id"]]
        task_instances = sort_dag_or_task_list(task_instances)
        dag["tasks"] = task_instances

for tag, dag_list in tag_to_running_info.items():
    tag_to_running_info[tag] = sort_dag_or_task_list(dag_list)
end = time.perf_counter()
print(f"Time elapsed: {end-start}s")
