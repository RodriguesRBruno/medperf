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
    dags_raw_result: DAGCollection,
) -> dict[str, list[dict[str, str]]]:
    tag_to_dag_dict = defaultdict(lambda: list())
    for dag in dags_raw_result["dags"]:
        if not dag["tags"]:
            tag_to_dag_dict["Untagged"].append(dag)
            continue

        for tag in dag["tags"]:
            tag_name = tag["name"]
            tag_to_dag_dict[tag_name].append(dag)
    return tag_to_dag_dict


with client.ApiClient(configuration) as api_client:

    dag_api_instance = dag_api.DAGApi(api_client)
    dag_run_api_instance = dag_run_api.DAGRunApi(api_client)
    task_instance_api_instance = task_instance_api.TaskInstanceApi(api_client)

    dags = wrapped_api_call(
        dag_api_instance.get_dags,
        # only_active=True,
        order_by="dag_id",
        # fields=["dag_id", "dag_display_name", "tags"],
    )

    tag_to_dags_dict = _get_tag_to_dags_dict(dags)
    sorted_tags = sorted(
        tag_to_dags_dict,
        key=lambda x: (x == "Untagged", "Finish" in x, "Setup" not in x),
    )
    tag_to_dags_dict = {
        sorted_key: tag_to_dags_dict[sorted_key] for sorted_key in sorted_tags
    }

    tag_to_running_info = {tag: [] for tag in tag_to_dags_dict}
    for tag, dag_list in tag_to_dags_dict.items():

        for dag in dag_list:
            dag_id = dag["dag_id"]

            # TODO looking at dag_runs only, I don't get unstarted DAGs
            # Should probably query both, filter out started, mark the
            # unstarted DAGS accordingly
            dag_runs = wrapped_api_call(
                dag_run_api_instance.get_dag_runs,
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
            )
            dag_runs = dag_runs["dag_runs"]
            dag_task_definitions = wrapped_api_call(
                dag_api_instance.get_tasks, dag_id=dag_id
            )
            dag_task_definitions = dag_task_definitions["tasks"]

            if dag_runs:
                task_id_to_doc_md = {
                    task["task_id"]: task["doc_md"] for task in dag_task_definitions
                }
                most_recent_run = dag_runs[0]
                dag_run_id = most_recent_run["dag_run_id"]
                dag_run_tasks = wrapped_api_call(
                    task_instance_api_instance.get_task_instances,
                    dag_id=dag_id,
                    dag_run_id=dag_run_id,
                )
                dag_run_tasks = dag_run_tasks["task_instances"]
                for dag_run_task in dag_run_tasks:
                    dag_run_task["doc_md"] = task_id_to_doc_md[dag_run_task["task_id"]]
                dag_run_tasks = sort_dag_or_task_list(dag_run_tasks)
                most_recent_run["task_instances"] = dag_run_tasks
                tag_to_running_info[tag].append(most_recent_run)
            else:
                for dag_task in dag_task_definitions:
                    dag_task["state"] = State.PENDING

                dag["state"] = State.PENDING
                dag["task_instances"] = dag_task_definitions
                tag_to_running_info[tag].append(dag)

            tag_to_running_info[tag] = sort_dag_or_task_list(tag_to_running_info[tag])

# print(tag_to_running_info)
end = time.perf_counter()
print(f"Time elapsed: {end-start}s")
