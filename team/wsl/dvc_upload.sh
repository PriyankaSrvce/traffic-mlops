#!/usr/bin/env bash
# Upload every DVC-tracked data file to the team's DVC remote (Google Drive).
# For the DVC teammate (docs/DVC_DATA_GUIDE.md, part A). Safe to run again: only missing files
# are uploaded. Only the *.dvc data pointers are used, never dvc.yaml pipeline outputs.
. "$(dirname "$0")/common.sh"
need_venv
DVC="$DVC_VENV/bin/dvc"
[ -x "$DVC" ] || fail "DVC is not installed. Run team/windows/0_SETUP_WSL.cmd first."
mapfile -t TARGETS < <("$PY" scripts/team_helpers.py dvc-targets)
[ "${#TARGETS[@]}" -gt 0 ] || fail "Could not list the DVC pointer files."

say "1/4  Checking the data files against their pointer files (MD5)"
"$PY" scripts/team_helpers.py check-data \
  || fail "Fix the files above first (unzip TEAM_DATA_FOR_DVC.zip into this folder, or ask for a new zip)."

say "2/4  Adding the files to DVC's local cache"
"$DVC" commit --force "${TARGETS[@]}"
# On a Windows drive every file looks executable to Linux, so DVC adds "isexec: true" to some
# pointer files. The fingerprints were checked in step 1 and are unchanged; restore the
# committed pointer files so nothing shows up as modified in Git.
git checkout -- "${TARGETS[@]}"

say "3/4  Uploading (first time: sign in to Google in the browser; see the guide, part B, if blocked)"
"$DVC" push "${TARGETS[@]}"

say "4/4  Comparing local data with the remote"
"$DVC" status --cloud "${TARGETS[@]}"
echo
echo "If the last line says the cache and remote are in sync, tell the team: 1_GET_DATA.cmd now works."
finish
