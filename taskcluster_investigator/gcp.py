from functools import cache
from google.cloud import logging as logging

from .cache import read_cache_file, write_cache_file


@cache
def get_client():
    client = logging.Client(_use_grpc=0)
    return client


def ensure_client():
    client = get_client()
    if not client.project:
        raise Exception("GCP project not set")


def format_query(query, cluster_name="", timestamp=""):
    return " AND ".join(
        [
            f'timestamp>"{timestamp}"',
            f'resource.labels.cluster_name="{cluster_name}"',
            f"{query}",
        ]
    )


def query_logs(query, cluster_id, timestamp, use_cache=True):
    client = get_client()

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


PAGE_SIZE = 200
