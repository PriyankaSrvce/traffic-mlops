# Shared settings for the team scripts. Each script starts with:  . "$(dirname "$0")/common.sh"
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV="${TRAFFIC_VENV:-$HOME/venvs/traffic}"
EVIDENTLY_VENV="${TRAFFIC_EVIDENTLY_VENV:-$HOME/venvs/traffic-evidently}"
DVC_VENV="${TRAFFIC_DVC_VENV:-$HOME/venvs/traffic-dvc}"
PY="$VENV/bin/python"
DATA="$REPO/data/sumo"
OUT="$REPO/outputs"
export PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 LANG=C.UTF-8
export PATH="$HOME/.local/bin:$PATH"
cd "$REPO"

say()  { printf '\n==> %s\n' "$*"; }
fail() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

need_venv() {
  [ -x "$PY" ] || fail "Python environment not found at $VENV. Run team/windows/0_SETUP_WSL.cmd (or team/wsl/setup_env.sh) first."
}

need_data() {
  local missing=0
  for f in queue_training_labels_v1.csv queue_training_labels_v2.csv drift_surge_600.csv drift_surge_720.csv drift_sensor_fault_kmh.csv; do
    [ -f "$DATA/$f" ] || { echo "  missing: data/sumo/$f"; missing=1; }
  done
  [ "$missing" = 0 ] || fail "Project data is missing. Run team/windows/1_GET_DATA.cmd first (see docs/TEAM_SETUP.md, step 3)."
  [ -f "$DATA/splits/test.csv" ] || fail "Data splits are missing. Run team/windows/1_GET_DATA.cmd first."
}

# Production model file (downloaded and SHA-checked by scripts/fetch_model.py); prints its path.
production_model() { "$PY" scripts/fetch_model.py 2>/dev/null | tail -1; }

# Local Metaflow service + S3 storage started by team/windows/START_METAFLOW_UI.cmd.
# The S3 store (SeaweedFS) runs without authentication on 127.0.0.1; these keys are placeholders
# that the client library requires, not secrets.
metaflow_service_env() {
  export METAFLOW_SERVICE_URL=http://localhost:8080 METAFLOW_DEFAULT_METADATA=service \
         METAFLOW_DEFAULT_DATASTORE=s3 METAFLOW_DATASTORE_SYSROOT_S3=s3://metaflow/data \
         METAFLOW_S3_ENDPOINT_URL=http://localhost:9000 AWS_ACCESS_KEY_ID=local-demo \
         AWS_SECRET_ACCESS_KEY=local-demo-not-a-secret AWS_DEFAULT_REGION=us-east-1 \
         USERNAME="${USERNAME:-${USER:-teammate}}"
  curl -s -o /dev/null --max-time 5 http://localhost:8080/ping \
    || fail "The Metaflow service is not running. Start Docker Desktop, then run team/windows/START_METAFLOW_UI.cmd."
}

finish() { if [ -t 0 ]; then read -r -p "Done. Press Enter to close..." _ || true; fi; }
