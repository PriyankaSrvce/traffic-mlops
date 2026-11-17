@echo off
title Monitoring stack
REM API + Prometheus + Grafana in Docker. The API downloads the production model itself.
set "PATH=%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin;C:\Program Files\Docker\Docker\resources\bin;%PATH%"
pushd "%~dp0..\..\monitoring" || exit /b 1
echo Starting API + Prometheus + Grafana (Docker Desktop must say "Engine running")...
docker compose up -d --build
if errorlevel 1 ( echo Docker failed. Is Docker Desktop running? & popd & pause & exit /b 1 )
popd
echo Waiting for the services to start...
timeout /t 25 /nobreak >nul
start "" "http://localhost:3000/d/traffic-mlops?kiosk&refresh=5s&from=now-10m&to=now"
start "" "http://localhost:8000/dashboard"
echo.
echo Grafana:       http://localhost:3000
echo Web dashboard: http://localhost:8000/dashboard
echo Prometheus:    http://localhost:9090
echo Next: RUN_LIVE_TRAFFIC.cmd sends simulated traffic. Stop everything with STOP_MONITORING.cmd.
pause
