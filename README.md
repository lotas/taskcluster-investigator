# Query GCP logs and Taskcluster

Some useful queries to debug taskcluster tasks and workers

Authentication is required for GCP and can be done with:

```sh
gcloud config configurations activate prod
gcloud config set project your-project-id
gcloud beta auth application-default login
```

Taskcluster client expects following env variables:
```
TASKCLUSTER_ROOT_URL=https://community-tc.services.mozilla.com/
TASKCLUSTER_CLIENT_ID=id
TASKCLUSTER_ACCESS_TOKEN=token
```

## Running queries:

```sh
# run all queries
python get-stats.py community-tc

# run specific query for the past 48 hours
LAST_HOURS=48 python get-stats.py community-tc investigate-claim

# check single worker, check queries/investigate-worker.yml for IDs
LAST_HOURS=4 python get-stats.py community-tc investigate-worker

# check single task
LAST_HOURS=4 python get-stats.py community-tc investigate-task
```

## Clusters

GCP kubernetes clusters are defined in `clusters.yml`

## Queries

Various queries are grouped and stored in `queries/` directory.
