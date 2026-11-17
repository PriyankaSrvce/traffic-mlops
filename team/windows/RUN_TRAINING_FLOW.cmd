@echo off
title Metaflow training runs
REM Trains v1 and v2 with Metaflow into the local Metaflow UI. Start START_METAFLOW_UI.cmd first.
pushd "%~dp0..\.." || exit /b 1
wsl --cd "%CD%" -- bash team/wsl/training_flow.sh
popd
