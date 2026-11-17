@echo off
title Upload data to DVC
REM For the DVC teammate: checks the data, then uploads it to the team's Google Drive remote.
pushd "%~dp0..\.." || exit /b 1
wsl --cd "%CD%" -- bash team/wsl/dvc_upload.sh
popd
