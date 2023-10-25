# Query GCP logs and Taskcluster


Some useful queries to debug taskcluster tasks and workers

## Running queries:

```sh
# run all queries
python get-stats.py community-tc

# run specific query for the past 48 hours
LAST_HOURS=48 python get-stats.py community-tc investigate-claim
```

## Clusters

GCP kubernetes clusters are defined in `clusters.yml`

## Queries

Various queries are grouped and stored in `queries/` directory.
