#!/usr/bin/env bash
# Send simulated production traffic to the local API (start it first with START_MONITORING.cmd):
# normal traffic, then a demand surge, then a faulty speed sensor, with ground-truth feedback.
# About 5 minutes. Watch Grafana (http://localhost:3000) while it runs.
. "$(dirname "$0")/common.sh"
need_data
curl -s -o /dev/null --max-time 5 http://localhost:8000/health \
  || fail "The local API is not running. Run team/windows/START_MONITORING.cmd first."
python3 scripts/replay_production_traffic.py --base-url http://localhost:8000 \
  --phase normal="$DATA/splits/validation.csv" \
  --phase demand_surge="$DATA/drift_surge_600.csv" \
  --phase sensor_fault="$DATA/drift_sensor_fault_kmh.csv" \
  --rows-per-phase 600 --occupied-only --min-phase-seconds 100
finish
