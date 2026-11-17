#!/usr/bin/env bash
# Train the queue model with Metaflow into the local Metaflow service, so the runs appear in the
# Metaflow UI (http://localhost:8083). Start the UI first: START_METAFLOW_UI.cmd.
#   v1 = Phase 2 data (357,124 rows)   v2 = v1 data + 12 surge runs (607,924 rows)
# Each run takes 1-2 minutes. With the pinned environment it reproduces the registered model
# file exactly (same SHA-256), which is checked at the end.
# Usage: training_flow.sh [v1] [v2]   (default: both)
. "$(dirname "$0")/common.sh"
need_venv; need_data; metaflow_service_env
"$PY" scripts/team_helpers.py ensure-bucket
for v in ${@:-v1 v2}; do
  say "Training run on the $v dataset"
  "$PY" flows/bengaluru_queue_model_flow.py --metadata=service --datastore=s3 run \
    --dataset "$DATA/queue_training_labels_$v.csv" --artifact-root "$OUT/metaflow_artifacts" 2>&1 \
    | sed -E 's/\[MFLOG[^]]*\]//' | grep -E "Workflow starting|Task finished|model_sha256|registry_status|Done|rror" || true
done
say "Do the runs reproduce the registered models?"
"$PY" scripts/team_helpers.py check-reproduced "$OUT/metaflow_artifacts"
echo; echo "Open the Metaflow UI: http://localhost:8083"
finish
