@echo off
title Get data and model
REM Downloads the data with DVC (or uses an unzipped TEAM_DATA_FOR_DVC.zip), checks it, builds splits, downloads the model.
pushd "%~dp0..\.." || exit /b 1
wsl --cd "%CD%" -- bash team/wsl/get_data.sh
popd
