import sys
import yaml
import json
from os import listdir
from os.path import isfile, join
from google.cloud import logging as logging
from datetime import datetime, timedelta, timezone

DIR = "queries"
PROJECT_ID = "moz-fx-taskcluster-prod-4b87"

time_from = datetime.now(timezone.utc) - timedelta(hours=12)
time_format = "%Y-%m-%dT%H:%M:%S.%f%z"
timestamp = time_from.strftime(time_format)


def parse_yaml(f):
    with open(f, "r") as file:
        yaml_data = yaml.safe_load(file)

    return yaml_data


def load_queries():
    return [
        parse_yaml(join(DIR, f))
        for f in listdir(DIR)
        if isfile(join(DIR, f)) and f.endswith(".yml")
    ]


def get_client():
    # print(f"Connecting to {PROJECT_ID}")
    client = logging.Client(project=PROJECT_ID, _use_grpc=0)
    return client


def format_query(query, cluster_name="", timestamp=""):
    return " AND ".join(
        [
            f'timestamp>"{timestamp}"',
            f'resource.labels.cluster_name="{cluster_name}"',
            f"{query}",
        ]
    )


PAGE_SIZE = 200
TABLE_WIDTH = 70
VAL_WIDTH = 20
COL_WIDTH = TABLE_WIDTH - VAL_WIDTH
SPINNER = ["|", "/", "-", "\\"]


def run_queries(cluster_id, query_groups=[], client=None):
    for group in query_groups:
        if "name" in group:
            width = len(group["name"]) + 2
            print(f'\n{"-" * width}\n{group["name"]} |\n{"-" * width}\n')

        for query in group["queries"]:
            filter = format_query(
                query["query"],
                cluster_name=cluster_id,
                timestamp=timestamp,
            )

            title = f'{query["name"]:<{COL_WIDTH}}'
            print(title, end=" ", flush=True)
            results_iterator = client.list_entries(
                filter_=filter,
                page_size=PAGE_SIZE,
                order_by="timestamp desc",
            )

            count = 0
            spinner = 0
            for row in results_iterator:
                count += 1
                if count % 10 == 0:
                    print(
                        f"\r{title}{count:>{VAL_WIDTH}} {SPINNER[spinner % len(SPINNER)]}",
                        end="",
                        flush=True,
                    )
                    spinner += 1

            print(f"\r{title}{count:>{VAL_WIDTH}}{' ' * 4}")


def main():
    client = get_client()
    clusters = parse_yaml("clusters.yml")["clusters"]

    cluster_name = sys.argv[1] if len(sys.argv) > 1 else ""

    if cluster_name:
        if cluster_name not in clusters:
            print(f"Unknown cluster: {cluster_name}")
            return
        cluster_list = [(cluster_name, clusters[cluster_name])]
    else:
        cluster_list = clusters.items()

    for name, id in cluster_list:
        print(f"\n{name} ({id})")
        run_queries(id, query_groups=load_queries(), client=client)
        print(f"\n{'-' * TABLE_WIDTH}\n")


if __name__ == "__main__":
    main()
