@echo off
title Metaflow UI setup (one time)
REM Downloads Netflix metaflow-service at a pinned commit and applies the project's small UI patch.
pushd "%~dp0..\.." || exit /b 1
if exist ".metaflow-service\.git" (
  echo .metaflow-service already exists. Delete that folder to set it up again.
  goto done
)
git -c core.autocrlf=false clone https://github.com/Netflix/metaflow-service.git .metaflow-service || goto failed
git -C .metaflow-service -c core.autocrlf=false checkout -q 2a263c5 || goto failed
git -C .metaflow-service apply "%CD%\team\metaflow-ui\ui-artifact-size.patch" || goto failed
echo Metaflow UI source ready. Next: START_METAFLOW_UI.cmd
:done
popd
pause
exit /b 0
:failed
echo Setup failed. Check your internet connection and that Git for Windows is installed.
popd
pause
exit /b 1
