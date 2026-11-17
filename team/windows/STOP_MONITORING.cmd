@echo off
title Stop monitoring stack
set "PATH=%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin;C:\Program Files\Docker\Docker\resources\bin;%PATH%"
pushd "%~dp0..\..\monitoring" || exit /b 1
docker compose down
popd
pause
