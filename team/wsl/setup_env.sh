#!/usr/bin/env bash
# One-time setup inside WSL Ubuntu 24.04: three Python environments with the project's pinned
# versions, plus the system libraries SUMO's map window needs.
#   ~/venvs/traffic            project code, tests, Metaflow, SUMO
#   ~/venvs/traffic-evidently  Evidently drift reports (needs its own pandas pin)
#   ~/venvs/traffic-dvc        DVC with the Google Drive plugin
# Safe to run again: existing environments are reused and only missing packages are installed.
. "$(dirname "$0")/common.sh"
UV_VERSION=0.11.7

say "1/5  System libraries for SUMO's map window (asks for your Ubuntu password)"
if ! dpkg -s libgl1 libx11-6 libxext6 libxrender1 libatomic1 >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq libgl1 libx11-6 libxext6 libxrender1 libatomic1 curl git
else
  echo "already installed"
fi

say "2/5  uv (Python installer) $UV_VERSION"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf "https://astral.sh/uv/$UV_VERSION/install.sh" | sh
fi
uv --version

make_env() {  # make_env <folder> <requirements files...>
  local dir="$1"; shift
  [ -x "$dir/bin/python" ] || uv venv -q --python 3.12 "$dir"
  local args=(); for r in "$@"; do args+=(-r "$r"); done
  uv pip install -q --python "$dir/bin/python" "${args[@]}"
}

say "3/5  Main environment: $VENV"
make_env "$VENV" requirements-phase2.txt requirements-test-phase1.txt requirements-sim.txt
say "4/5  Evidently environment: $EVIDENTLY_VENV"
make_env "$EVIDENTLY_VENV" requirements-monitoring.txt
say "5/5  DVC environment: $DVC_VENV"
make_env "$DVC_VENV" requirements-dvc.txt

say "Checking"
"$PY" - <<'PY'
import importlib.metadata as m
for p in ["metaflow", "scikit-learn", "pandas", "fastapi", "pytest", "eclipse-sumo", "boto3"]:
    print(f"  {p:14s} {m.version(p)}")
PY
SUMO_HOME="$("$PY" -c 'import sumo; print(sumo.SUMO_HOME)')" "$VENV/bin/sumo" --version | head -1
"$EVIDENTLY_VENV/bin/python" -W ignore -c "import evidently; print('  evidently', evidently.__version__)"
"$DVC_VENV/bin/dvc" --version | sed 's/^/  dvc /'
echo
echo "Setup complete. Next: team/windows/1_GET_DATA.cmd"
finish
