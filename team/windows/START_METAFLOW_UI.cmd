@echo off
title Metaflow UI
set "PATH=%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin;C:\Program Files\Docker\Docker\resources\bin;%PATH%"
pushd "%~dp0..\.." || exit /b 1
if not exist ".metaflow-service\.git" ( echo Run SETUP_METAFLOW_UI.cmd first. & popd & pause & exit /b 1 )
echo Starting the Metaflow UI (the first time builds images: 5-10 minutes)...
docker compose -f team\metaflow-ui\docker-compose.yml up -d --build
if errorlevel 1 ( echo Docker failed. Is Docker Desktop running? & popd & pause & exit /b 1 )
popd
timeout /t 15 /nobreak >nul
start "" "http://localhost:8083"
echo Metaflow UI: http://localhost:8083
echo No runs yet? Run RUN_TRAINING_FLOW.cmd. Stop with STOP_METAFLOW_UI.cmd (your runs are kept).
pause
