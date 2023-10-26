import sys
import yaml
import json
import os
import hashlib

import logging
from os import listdir
from os.path import isfile, join
from datetime import datetime, timedelta, timezone

from .utils import PROJECT_ROOT

CACHE_DIR = os.path.join(PROJECT_ROOT, ".cache")
CACHE_MINUTES = 120

logger = logging.getLogger("cache")


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
    file_name = get_cache_file_name(query_name, input_data)

    logger.debug("Writing cache: %s (%d bytes)", file_name, len(output))

    with open(file_name, "w") as file:
        json.dump(
            {
                "input": input,
                "output": output,
                "expires": (
                    datetime.now() + timedelta(minutes=CACHE_MINUTES)
                ).isoformat(),
            },
            file,
        )


def read_cache_file(query_name, input_data=[]):
    # check if file exists
    file_name = get_cache_file_name(query_name, input_data)
    logger.debug("Reading cache: %s", file_name)
    if not os.path.exists(file_name):
        logger.debug("Cache file not found: %s", file_name)
        return None

    # read file
    with open(file_name, "r") as file:
        data = json.load(file)
        logger.debug("Cache file found: %s", file_name)

        if datetime.fromisoformat(data["expires"]) < datetime.now():
            os.remove(file_name)
            logger.debug("Cache file expired: %s", file_name)
            return None

        return json.loads(data["output"])

    return None


def remove_expired_cache_files():
    ensure_cache_dir()

    for f in listdir(CACHE_DIR):
        if not isfile(join(CACHE_DIR, f)) or not f.endswith(".json"):
            continue

        file_name = join(CACHE_DIR, f)
        with open(file_name, "r") as file:
            data = json.load(file)

            if (
                "expires" in data
                and datetime.fromisoformat(data["expires"]) < datetime.now()
            ):
                os.remove(file_name)
