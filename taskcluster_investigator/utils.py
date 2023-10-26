import os
import yaml
from os import listdir
from os.path import isfile, join, dirname

PROJECT_ROOT = join(dirname(__file__), "..")
PIPELINES_DIR = "pipelines"
CLUSTERS_FILE = "clusters.yml"


def parse_yaml(f):
    with open(f, "r") as file:
        yaml_data = yaml.safe_load(file)

    return yaml_data


def load_pipeline_files():
    files = []
    for f in listdir(PIPELINES_DIR):
        if isfile(join(PIPELINES_DIR, f)) and f.endswith(".yml"):
            data = parse_yaml(join(PIPELINES_DIR, f))
            data["id"] = f.replace(".yml", "")
            files.append(data)

    return files


def load_clusters():
    return parse_yaml(join(PROJECT_ROOT, CLUSTERS_FILE))["clusters"]
