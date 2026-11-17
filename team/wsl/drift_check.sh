#!/usr/bin/env bash
# Phase 3 drift check with the production model, end to end:
#   1. PSI + error drift detector (drift_detection.py) on 5 batches
#   2. Evidently reports on the same batches (HTML files)
#   3. Retraining trigger decision (dry run: it does not start training)
# Results go to outputs/drift_check/ (not committed).
. "$(dirname "$0")/common.sh"
need_venv; need_data
MODEL="$(production_model)"
[ -f "$MODEL" ] || fail "Could not get the production model (run 1_GET_DATA.cmd)."
R="$OUT/drift_check"; rm -rf "$R"; mkdir -p "$R"
APPROVED_MAE="$("$PY" scripts/fetch_model.py --print-test-mae)"

say "1/3  Drift detector (reference = the production model's training split)"
"$PY" sumo/bengaluru_osm/drift_detection.py --reference "$DATA/splits_v2/train.csv" --approved-test-mae "$APPROVED_MAE" \
  --batch normal_test="$DATA/splits/test.csv" --batch normal_validation="$DATA/splits/validation.csv" \
  --batch surge_600="$DATA/drift_surge_600.csv" --batch surge_720="$DATA/drift_surge_720.csv" \
  --batch sensor_fault_kmh="$DATA/drift_sensor_fault_kmh.csv" \
  --model "$MODEL" --output-dir "$R" | grep -v "^report"

say "2/3  Evidently reports (same vehicle mix on both sides; about 1 minute)"
if [ -x "$EVIDENTLY_VENV/bin/python" ]; then
  "$EVIDENTLY_VENV/bin/python" -W ignore sumo/bengaluru_osm/evidently_drift_report.py \
    --reference "$DATA/splits/test.csv,$R/normal_test_predictions.csv" \
    --batch normal_validation="$DATA/splits/validation.csv,$R/normal_validation_predictions.csv" \
    --batch surge_600="$DATA/drift_surge_600.csv,$R/surge_600_predictions.csv" \
    --batch surge_720="$DATA/drift_surge_720.csv,$R/surge_720_predictions.csv" \
    --batch sensor_fault_kmh="$DATA/drift_sensor_fault_kmh.csv,$R/sensor_fault_kmh_predictions.csv" \
    --composition balanced_assumed --html-segments occupied_lanes --output-dir "$R/evidently" 2>&1 \
    | grep "batch=" | sed 's/^.*evidently_drift //'
  echo "Open the reports in a browser from: $(wslpath -w "$R/evidently" 2>/dev/null || echo "$R/evidently")"
else
  echo "Evidently environment missing; run 0_SETUP_WSL.cmd"
fi

say "3/3  Retraining trigger (decision only)"
set +e
"$PY" scripts/retraining_trigger.py --drift-report "$R/drift_report.json" --request-file "$R/retraining_request.json"
code=$?
set -e
if [ "$code" = 10 ]; then echo "=> TRIGGER: retraining recommended (exit code 10)"; else echo "=> no retraining needed (exit code $code)"; fi
finish
