@echo off
title Stop Metaflow UI
set "PATH=%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin;C:\Program Files\Docker\Docker\resources\bin;%PATH%"
pushd "%~dp0..\.." || exit /b 1
docker compose -f team\metaflow-ui\docker-compose.yml stop
popd
echo Stopped. Your runs are kept.
pause
