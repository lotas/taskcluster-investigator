import sys
import logging
import json

from taskcluster_investigator import cache, taskcluster, gcp, pipelines

logger = logging.getLogger("main")


def main():
    cache.remove_expired_cache_files()
    taskcluster.ensure_auth()
    gcp.ensure_client()

    pipeline_name = sys.argv[1] if len(sys.argv) > 1 else ""

    # pipeline = pipelines.get_pipeline_by_name('investigate-task')
    pipeline = pipelines.get_pipeline_by_name(pipeline_name)
    pipeline.set_params(
        {
            "cluster_id": "taskcluster-communitytc-v1",
            "timestamp": "2023-10-26T00:00:00Z",
        }
    )
    res = pipeline.run()
    print(json.dumps(res, default=str, indent=2))


if __name__ == "__main__":
    main()
