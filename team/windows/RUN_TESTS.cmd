@echo off
title Tests
REM Runs the full PyTest suite (same as GitHub Actions).
pushd "%~dp0..\.." || exit /b 1
wsl --cd "%CD%" -- bash team/wsl/run_tests.sh
popd
