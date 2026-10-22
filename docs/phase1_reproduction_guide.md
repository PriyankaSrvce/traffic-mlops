# Phase 1 Baseline Reproduction Guide

## Scope

This guide covers the existing same-day daily `Traffic Volume` regression baseline only. It does not reproduce a five-minute queue-length model or implement SUMO, signal control, rerouting, or deployment. The successful reproduction was performed in a disposable project copy; do not run the feature or training commands from the shared/original project because they overwrite project outputs.

## Inputs and outputs

The scripts resolve their project root from their own file locations and expect these inputs in the project copy:

- `data/raw/bangalore_traffic.csv` — historical raw input. Its local MD5 was verified against the DVC pointer as `e4eba120722bf681e43f973b35a37e6d`. The original dataset source and license are not verified; license status remains **unverified**.
- `src/features/bangalore_events.csv` — event-calendar input.
- `src/features/build_features.py` and `src/models/train.py` — existing scripts.

For a clean copy, include the raw CSV, `src/features/bangalore_events.csv`, `src/features/build_features.py`, `src/models/train.py`, and (if running tests) `tests/test_features.py` and `tests/test_train.py`; preserve these relative paths. If the raw CSV is unavailable, stop rather than substituting another dataset or fetching from DVC. Do not copy `.dvc/` configuration, credentials, the old processed CSV, model, `docs/model_results.md`, `mlflow.db`, or `mlruns/`.

Feature generation writes `data/processed/traffic_features.csv`. Training writes `model.pkl` and overwrites `docs/model_results.md`; it also writes tracking data to `mlflow.db` and creates MLflow artifacts under `mlruns/`. Keep all of these outputs inside a disposable copy. A clean copy should not contain an old processed CSV, model, generated model-results report, MLflow database, or `mlruns/` history.

The scripts use local files directly and do not import DVC on this path. DVC and `dvc-gdrive` are therefore unnecessary for this direct baseline reproduction. Do not use DVC to fetch or alter data as part of these steps.

## Scratch environment used for the recorded reproduction

The verified scratch layout was `phase1-baseline-repro/` with `project/` and `.venv/` as siblings. The scratch-only `project/requirements-baseline.txt` contained:

```text
holidays==0.105
joblib==1.6.0
mlflow==3.16.1
numpy==2.2.6
pandas==2.3.3
scikit-learn==1.7.2
xgboost==3.2.0
```

The reproduction environment reported Python 3.12.6. For a new scratch copy, use a Python 3.12 interpreter and install these pins only into its scratch virtual environment. The full project `requirements.txt` includes DVC and many unrelated packages; it is not required by the direct feature/training path. Environment creation or package installation commands were not run during this handoff audit and require approval before execution.

## Commands for an isolated copy

Prepare the disposable layout above, place the inputs and source files in `project/`, and create the scratch-only requirements file there. From the scratch workspace parent in Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\project\requirements-baseline.txt
Set-Location .\project
& ..\.venv\Scripts\python.exe --version
& ..\.venv\Scripts\python.exe -m src.features.build_features
& ..\.venv\Scripts\python.exe -m src.models.train
```

The module entry points are verified in the scripts. Run feature generation before training so the processed CSV exists. After feature generation, check that the output has 8,936 rows and 12 columns, no missing values, and a numeric, finite, nonnegative `Traffic Volume` target. Do not continue if the output differs; investigate without changing feature logic to force expected counts.

The adopted local implementation's chronological split is train 2022-01-01 through 2024-01-31 (7,145 rows, 761 dates) and test 2024-02-01 through 2024-08-09 (1,791 rows, 191 dates). The scratch run matched the adopted local report at displayed precision; it did not reproduce the different legacy metrics from the pre-adoption GitHub clone. The trainer selects its champion by lowest RMSE on the chronological test split, so those scores are not from a test set kept untouched for final model selection.

The focused tests were run in a separate test-only copy with `tests/test_features.py`, `tests/test_train.py`, `src/features/build_features.py`, and `src/models/train.py`. All five passed under Python 3.12.6. The command was:

```powershell
& ..\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The isolated baseline reproduction ran feature generation and training. The focused unit tests were run separately as described above. No EDA, retraining, or package installation was performed during repository integration. No separate console-log file was saved for the successful scratch baseline run. The original `model.pkl` was not loaded or verified as a working model.



