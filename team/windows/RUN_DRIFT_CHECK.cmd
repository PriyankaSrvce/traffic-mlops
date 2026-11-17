@echo off
title Drift check
REM Drift detector + Evidently reports + retraining trigger decision. Results in outputs\drift_check.
pushd "%~dp0..\.." || exit /b 1
wsl --cd "%CD%" -- bash team/wsl/drift_check.sh
popd
