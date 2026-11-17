@echo off
title Live traffic (keep open)
REM Sends simulated traffic to the local API for about 5 minutes. Start START_MONITORING.cmd first.
pushd "%~dp0..\.." || exit /b 1
wsl --cd "%CD%" -- bash team/wsl/live_traffic.sh
popd
