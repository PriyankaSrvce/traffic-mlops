#!/usr/bin/env bash
# Get the project data and the production model, then build the train/validation/test splits.
#   1. `dvc pull` downloads every DVC-tracked file from the team's Google Drive remote.
#      (First time: a browser window asks you to sign in to Google; see docs/DVC_DATA_GUIDE.md.)
#      If DVC is not available yet, unzip TEAM_DATA_FOR_DVC.zip into the repository folder instead
#      and run this script again: it then skips the download.
#   2. Every data file is checked against the MD5 in its .dvc pointer file.
#   3. Splits by whole simulation seed are written with the team's own split script.
#   4. The production model is downloaded and its SHA-256 checked against the registry.
. "$(dirname "$0")/common.sh"
need_venv

say "1/4  Data files"
if [ -f "$DATA/queue_training_labels_v2.csv" ] && [ -f sumo/bengaluru_osm/bengaluru_osm_sim.net.xml ]; then
  echo "data already present (skipping dvc pull)"
else
  [ -x "$DVC_VENV/bin/dvc" ] || fail "DVC is not installed. Run team/windows/0_SETUP_WSL.cmd first."
  mapfile -t TARGETS < <("$PY" scripts/team_helpers.py dvc-targets)
  [ "${#TARGETS[@]}" -gt 0 ] || fail "Could not list the DVC pointer files."
  "$DVC_VENV/bin/dvc" pull "${TARGETS[@]}" || fail "dvc pull failed. Read docs/DVC_DATA_GUIDE.md, part B (sign-in problems), or ask the DVC teammate for TEAM_DATA_FOR_DVC.zip."
fi

say "2/4  Checking every file against its DVC pointer (MD5)"
"$PY" scripts/team_helpers.py check-data || fail "Some data files are missing or not the versioned ones (see above)."

say "3/4  Splits by whole simulation seed (train 7/42/2026, validation 99, test 123/31415)"
for v in v1 v2; do
  dir="$DATA/splits"; [ "$v" = v2 ] && dir="$DATA/splits_v2"
  if [ -f "$dir/test.csv" ]; then echo "$dir exists"; else
    "$PY" sumo/bengaluru_osm/split_training_data.py --input "$DATA/queue_training_labels_$v.csv" --output-dir "$dir" >/dev/null
    echo "wrote $dir"
  fi
done

say "4/4  Production model"
"$PY" scripts/fetch_model.py

echo; echo "Data and model ready."
finish
