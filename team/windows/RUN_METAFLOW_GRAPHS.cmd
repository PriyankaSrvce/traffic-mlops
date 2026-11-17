@echo off
title Metaflow graphs (keep open)
REM Results card with graphs at http://localhost:8325. Needs RUN_TRAINING_FLOW.cmd first.
pushd "%~dp0..\.." || exit /b 1
wsl --cd "%CD%" -- bash team/wsl/results_card.sh
popd
