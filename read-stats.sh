#!/bin/sh


gcloud logging read 'timestamp>"2023-10-18" resource.labels.cluster_name="taskcluster-communitytc-v1" jsonPayload.Type="task-exception" jsonPayload.Logger="taskcluster.queue.deadline-resolver"' --format="value(count())"
