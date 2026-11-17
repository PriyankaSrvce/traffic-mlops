#!/usr/bin/env bash
# Build the results card (graphs) from your latest training run and serve it at http://localhost:8325.
# Needs a training run first (RUN_TRAINING_FLOW.cmd). Keep this window open while presenting.
. "$(dirname "$0")/common.sh"
need_venv; metaflow_service_env
say "Building the results card from the latest successful training run"
mkdir -p "$OUT"
set +e
"$PY" flows/phase2_results_flow.py --metadata=service --datastore=s3 run --with card > "$OUT/results_card_run.log" 2>&1
status=$?
set -e
sed -E 's/\[MFLOG[^]]*\]//' "$OUT/results_card_run.log" | grep -E "Workflow starting|Task finished|Done|rror" || true
[ "$status" = 0 ] || fail "Building the card failed (details: outputs/results_card_run.log). Did RUN_TRAINING_FLOW.cmd finish?"
say "Serving the card at http://localhost:8325  (close this window to stop)"
exec "$PY" flows/phase2_results_flow.py --metadata=service --datastore=s3 card server --port 8325
