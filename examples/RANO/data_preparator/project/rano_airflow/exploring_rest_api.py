# REST API docs: https://airflow.apache.org/docs/apache-airflow/2.10.5/stable-rest-api-ref.html#section/Overview

import requests
import os
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
from datetime import datetime, UTC

load_dotenv()


class TestModes:
    clear_task = 1
    restart_dag_run = 2


test_mode = TestModes.clear_task

SUCCESS_STATE = "success"
FAILED_STATE = "failed"
UPSTREAM_FAILED_STATE = "upstream_failed"

auth = HTTPBasicAuth(os.getenv("AIRFLOW_USER"), os.getenv("AIRFLOW_PASS"))
BASE_URL = "http://localhost:8080/api/v1"

get_dags = requests.get(f"{BASE_URL}/dags", auth=auth)
print(get_dags.json())

dag_id = "~"  # Get runs for all dags
get_dag_runs = requests.get(f"{BASE_URL}/dags/{dag_id}/dagRuns", auth=auth)
print(get_dag_runs.json())

# Mock example: have a run deliberately fail first, so we can filter for failured
dag_id = "rano_pipeline"
get_rano_dag_runs = requests.get(f"{BASE_URL}/dags/{dag_id}/dagRuns", auth=auth)
rano_dag_runs_json = get_rano_dag_runs.json()

failed_runs = [
    run for run in rano_dag_runs_json["dag_runs"] if run["state"] == FAILED_STATE
]

# Inspect task runs to get which task failed
failed_runs_to_tasks = {}

for failed_run in failed_runs:
    failed_run_id = failed_run["dag_run_id"]
    failed_run_dag_id = failed_run["dag_id"]
    failed_run_config = failed_run["conf"]

    failed_run_tasks = requests.get(
        f"{BASE_URL}/dags/{failed_run_dag_id}/dagRuns/{failed_run_id}/taskInstances",
        auth=auth,
    )
    failed_run_tasks = failed_run_tasks.json()

    failed_tasks = [
        task
        for task in failed_run_tasks["task_instances"]
        if task["state"] == FAILED_STATE
    ]
    not_started_tasks = [
        task
        for task in failed_run_tasks["task_instances"]
        if task["state"] == UPSTREAM_FAILED_STATE
    ]
    success_tasks = [
        task
        for task in failed_run_tasks["task_instances"]
        if task["state"] == SUCCESS_STATE
    ]

    # Store info on this run and the failed task
    info_dict = {
        "dag_id": failed_run_dag_id,
        "conf": failed_run_config,
        "failed_tasks": failed_tasks,
    }

    failed_runs_to_tasks[failed_run_id] = info_dict

if test_mode == TestModes.clear_task:
    # Clear failed tasks from these runs
    for failed_run_id, run_info in failed_runs_to_tasks.items():

        payload = {
            "task_ids": [
                "make_csv"
            ],  # Force restart from here (simulating a missing modality, so we need to recreate the csv)
            "dag_run_id": failed_run_id,
            "include_downstream": True,
            "reset_dag_runs": True,  # Necessary to force re-run
            "only_failed": False,
            "dry_run": False,  # Must send this explicitly; default value is True!
        }

        response = requests.post(
            f"{BASE_URL}/dags/{run_info['dag_id']}/clearTaskInstances",
            auth=auth,
            json=payload,
        )
        response = response.json()

elif test_mode == TestModes.restart_dag_run:
    # Alternatively, restart the whole run
    for failed_run_id, run_info in failed_runs_to_tasks.items():
        new_id = f"Retry_{failed_run_id}_{datetime.now(UTC).isoformat()}"
        payload = {
            "dag_run_id": new_id,
            "conf": run_info["conf"],
            "note": f"Retrying run {failed_run_id} from the start via REST API.",
        }

        response = requests.post(
            f"{BASE_URL}/dags/{run_info['dag_id']}/dagRuns", auth=auth, json=payload
        )
        response = response.json()
