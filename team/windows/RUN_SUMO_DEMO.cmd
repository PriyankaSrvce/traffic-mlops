@echo off
title SUMO live simulation
REM Opens the SUMO map window with the model-driven (predictive) signal controller.
pushd "%~dp0..\.." || exit /b 1
wsl --cd "%CD%" -- bash team/wsl/sumo_demo.sh predictive
popd
