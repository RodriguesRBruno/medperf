# Note: can manually go to http://localhost:3000/graphql on Browser to explore GraphQL queries

import requests

url = "http://localhost:3000/graphql"
query = """
query GetAllRuns {
  runsOrError {
    ... on Runs {
      results {
        runId
        status
        stepStats {
          stepKey
          materializations {
            partition
            eventType
          }
        }
      }
    }
  }
}
"""

response = requests.post(url, json={"query": query})
data = response.json()

runs = data["data"]["runsOrError"]["results"]
failed_runs = [run for run in runs if run["status"] == "FAILURE"]
running_runs = [run for run in runs if run["status"] == "STARTED"]
success_runs = [run for run in runs if run["status"] == "SUCCESS"]
cancelled_runs = [run for run in runs if run["status"] == "CANCELLED"]
# queued_runs = [run for run in runs if run["status"] == "QUEUED"]  # TODO verify this
