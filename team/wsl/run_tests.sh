#!/usr/bin/env bash
# Run the full automated test suite (the same tests GitHub Actions runs on every push).
. "$(dirname "$0")/common.sh"
need_venv
say "PyTest"
"$PY" -m pytest tests -q
finish
