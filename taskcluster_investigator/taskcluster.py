import functools
import logging
import taskcluster

from .cache import read_cache_file, write_cache_file

logger = logging.getLogger("taskcluster")


def ensure_auth():
    auth = taskcluster.optionsFromEnvironment()
    if "rootUrl" not in auth:
        raise Exception("TASKCLUSTER_ROOT_URL not set")

    if "credentials" not in auth or "clientId" not in auth["credentials"]:
        raise Exception("TASKCLUSTER_CLIENT_ID not set")

    if "credentials" not in auth or "accessToken" not in auth["credentials"]:
        raise Exception("TASKCLUSTER_ACCESS_TOKEN not set")

    return True


@functools.cache
def get_queue_client():
    return taskcluster.Queue(taskcluster.optionsFromEnvironment())


@functools.lru_cache(maxsize=256)
def load_task(task_id):
    queue = get_queue_client()
    try:
        task = queue.task(task_id)
        task["taskId"] = task_id
        task["status"] = queue.status(task_id)["status"]
        task["runLength"] = len(task["status"]["runs"])
        logger.debug(f"Loaded task {task_id}")
        return task
    except taskcluster.exceptions.TaskclusterRestFailure as e:
        if e.status_code == 404:
            logger.warning(f"Task {task_id} not found")
            return None


def lookup_tasks(entries, field):
    tasks = []
    for entry in entries:
        task = load_task(entry[field])
        if task:
            tasks.append(task)
    return tasks
