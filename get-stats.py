import sys
import yaml
import json
import os
import hashlib
import taskcluster
import pickle
from os import listdir
from os.path import isfile, join
from google.cloud import logging as logging
from datetime import datetime, timedelta, timezone

DIR = "queries"
PROJECT_ID = "moz-fx-taskcluster-prod-4b87"

last_hours = int(os.environ.get("LAST_HOURS", 12))

time_from = datetime.now(timezone.utc) - timedelta(hours=last_hours)
time_from = time_from.replace(minute=0, second=0, microsecond=0)
time_format = "%Y-%m-%dT%H:%M:%S.%f%z"
timestamp = time_from.strftime(time_format)

queue = taskcluster.Queue(taskcluster.optionsFromEnvironment())


CACHE_DIR = ".cache"


def ensure_cache_dir():
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)


def get_cache_file_name(query_name, input_data=[]):
    ensure_cache_dir()

    input = json.dumps(input_data, default=str)
    input_md5 = hashlib.md5(input.encode("utf-8")).hexdigest()

    # create safe FS name from query name
    file_name = "".join(
        [
            query_name.replace(" ", "_").replace("/", "_"),
            "-",
            input_md5,
            ".json",
        ]
    )

    return os.path.join(CACHE_DIR, file_name)


def write_cache_file(query_name, input_data=[], output_data=[]):
    ensure_cache_dir()

    input = json.dumps(input_data, default=str)
    output = json.dumps(output_data, default=str)

    with open(get_cache_file_name(query_name, input_data), "w") as file:
        json.dump({"input": input, "output": output}, file)


def read_cache_file(query_name, input_data=[], cache_minutes=60):
    # check if file exists
    file_name = get_cache_file_name(query_name, input_data)
    if not os.path.exists(file_name):
        return None

    # check if file is expired
    file_time = datetime.fromtimestamp(os.path.getmtime(file_name))
    expires = datetime.now() - timedelta(minutes=cache_minutes)
    if file_time < expires:
        os.remove(file_name)
        return None

    # read file
    with open(file_name, "r") as file:
        data = json.load(file)
        return json.loads(data["output"])

    return None


def parse_yaml(f):
    with open(f, "r") as file:
        yaml_data = yaml.safe_load(file)

    return yaml_data


def load_queries(query_filter=""):
    return [
        parse_yaml(join(DIR, f))
        for f in listdir(DIR)
        if isfile(join(DIR, f)) and f.endswith(".yml") and query_filter in f
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


def query_logs(client, query, cluster_id, timestamp, use_cache=True):
    filter = format_query(
        query,
        cluster_name=cluster_id,
        timestamp=timestamp,
    )

    if use_cache:
        cache = read_cache_file("gcp-logs", [query, cluster_id, timestamp])
        if cache:
            print(" (cached) ", end="", flush=True)
            return cache

    output = client.list_entries(
        filter_=filter,
        page_size=PAGE_SIZE,
        order_by="timestamp desc",
    )

    # cannot dump iterators, so we'll fetch them all
    rows = []
    for row in output:
        rows.append(row.to_api_repr())
    write_cache_file("gcp-logs", [query, cluster_id, timestamp], rows)

    return rows


def get_nested_value(nested_dict, path):
    keys = path.split(".")
    value = nested_dict
    try:
        for key in keys:
            value = value.get(key) if key in value else value[key]
            if value is None:
                return None
        return value
    except:
        return None


def extract_fields(iterator, fields):
    out = []
    for row in iterator:
        out.append({name: get_nested_value(row, fields[name]) for name in fields})
    return out


def lookup_tasks(entries, field, use_cache=True):
    if use_cache:
        cache = read_cache_file("lookup-tasks", [entries, field])
        if cache:
            print(" (cached) ", end="", flush=True)
            return cache

    out = []
    for entry in entries:
        task_id = entry[field]
        task = queue.task(task_id)
        task["status"] = queue.status(task_id)["status"]
        task["taskId"] = task_id
        out.append(task)

    write_cache_file("lookup-tasks", [entries, field], out)

    return out


def summarize_tasks(tasks):
    def inc_counter(group, key):
        if key not in group:
            group[key] = 0
        group[key] += 1

    def print_counter(group, title):
        print(f"\n{title}")
        for key in dict(sorted(group.items())):
            print(f"{key}: {group[key]}")

    taskQueues = {}
    runs = {}
    resolutions = {}
    workerIds = {}

    for task in tasks:
        inc_counter(taskQueues, task["taskQueueId"])
        runs[task["taskId"]] = len(task["status"]["runs"])
        for run in task["status"]["runs"]:
            inc_counter(resolutions, run["reasonResolved"])
            inc_counter(workerIds, run["workerId"])

    print_counter(taskQueues, "Task Queues")
    print_counter(resolutions, "Run resolutions")
    print_counter(runs, "Runs")
    print_counter(workerIds, "Workers")

    return {
        "taskQueues": taskQueues,
        "resolutions": resolutions,
        "runs": runs,
        "workerIds": workerIds,
    }


def check_worker_claims(summary, query, client, cluster_id, timestamp):
    query_tpl = query["query"]

    [(field, collection)] = query["iterate"].items()

    if collection not in summary:
        print(f"Unknown collection: {collection}")
        return

    for row in summary[collection]:
        print(f"\nchecking for {field}={row}")
        res = query_logs(
            client,
            query_tpl.replace(f"%{field}%", row),
            cluster_id,
            timestamp,
            use_cache=True,
        )
        if "extract" in query:
            print("Extracted:")
            for row in extract_fields(res, query["extract"]):
                print(row)
        else:
            print(f"Found {len(res)} records")


def run_queries(cluster_id, query_groups=[], client=None):
    for group in query_groups:
        extracted = []

        if "name" in group:
            width = len(group["name"]) + 2
            print(f'\n{"-" * width}\n{group["name"]} |\n{"-" * width}\n')

        for query in group["queries"]:
            title = f'{query["name"]:<{COL_WIDTH}}'
            print(title, end=" ", flush=True)

            if "type" not in query:
                print("Unknown type")
                return

            # use cache
            use_cache = "cache" not in query or query["cache"]
            res = []

            if query["type"] == "count":
                res = query_logs(
                    client, query["query"], cluster_id, timestamp, use_cache
                )
                count = len(res)
                print(f"\r{title}{count:>{VAL_WIDTH}}{' ' * 4}")
            elif query["type"] == "query":
                res = query_logs(client, query["query"], cluster_id, timestamp)
                print(f"\Fetched {len(res)} records\n")
            elif query["type"] == "lookup-tasks":
                extracted = lookup_tasks(extracted, query["field"], use_cache)
                print(f"\nLooked up {len(extracted)} tasks")
            elif query["type"] == "summarize-tasks":
                extracted = summarize_tasks(extracted)
            elif query["type"] == "check-worker-claims":
                check_worker_claims(extracted, query, client, cluster_id, timestamp)
            else:
                print("Unknown type")

            if "extract" in query:
                extracted = extract_fields(res, query["extract"])
                print(f"\nExtracted {len(extracted)} records\n")


def main():
    client = get_client()
    clusters = parse_yaml("clusters.yml")["clusters"]

    cluster_name = sys.argv[1] if len(sys.argv) > 1 else ""
    query_filter = sys.argv[2] if len(sys.argv) > 2 else ""

    if cluster_name:
        if cluster_name not in clusters:
            print(f"Unknown cluster: {cluster_name}")
            return
        cluster_list = [(cluster_name, clusters[cluster_name])]
    else:
        cluster_list = clusters.items()

    for name, id in cluster_list:
        print(f"\n{name} ({id})")
        run_queries(id, query_groups=load_queries(query_filter), client=client)
        print(f"\n{'-' * TABLE_WIDTH}\n")


if __name__ == "__main__":
    main()
