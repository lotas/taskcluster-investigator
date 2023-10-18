import yaml
import json
from os import listdir
from os.path import isfile, join
from google.cloud import logging as logging
from datetime import datetime, timedelta, timezone

DIR = "queries"
PROJECT_ID = "moz-fx-taskcluster-prod-4b87"
# LOGGER_NAME = f"projects/{PROJECT_ID}/logs/stdout"
LOGGER_NAME = f"taskcluster.queue.claim-resolver"

time_from = datetime.now(timezone.utc) - timedelta(hours=12)
time_format = "%Y-%m-%dT%H:%M:%S.%f%z"
timestamp = time_from.strftime(time_format)


def parse_file(f):
    with open(join(DIR, f), "r") as file:
        yaml_data = yaml.safe_load(file)

    return yaml_data


def load_queries():
    # import all yaml files in queries folder
    return [
        parse_file(f)
        for f in listdir(DIR)
        if isfile(join(DIR, f)) and f.endswith(".yml")
    ]


def get_client():
    print(f"Connecting to {PROJECT_ID}: {LOGGER_NAME}")
    client = logging.Client(project=PROJECT_ID, _use_grpc=0)
    return client


def format_query(query, cluster_name="", timestamp=""):
    return " AND ".join(
        [
            f"timestamp>\"{timestamp}\"",
            f"resource.labels.cluster_name=\"{cluster_name}\"",
            f"{query}",
        ]
    )


PAGE_SIZE = 50

def main():
    client = get_client()
    for group in load_queries():
        for query in group["queries"]:
            filter = format_query(
                query["query"],
                cluster_name=group["cluster_name"],
                timestamp=timestamp,
            )
            print(group["cluster_name"], query["name"], filter)
            results_iterator = client.list_entries(
                filter_=filter,
                page_size=PAGE_SIZE,
                order_by="timestamp desc",
            )

            print("Counting...")
            count = 0
            for row in results_iterator:
                count += 1
                if count % PAGE_SIZE == 0:
                    print(".")
                # print(row.received_timestamp, row.insert_id)

            print(f"count: {count}")


if __name__ == "__main__":
    main()
