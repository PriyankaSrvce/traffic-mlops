@echo off
title Setup (one time)
REM One-time setup inside WSL Ubuntu: Python environments, SUMO libraries, DVC. Takes 5-15 minutes.
pushd "%~dp0..\.." || exit /b 1
wsl --cd "%CD%" -- bash team/wsl/setup_env.sh
popd
