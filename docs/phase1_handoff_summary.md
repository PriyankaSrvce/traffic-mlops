# Phase 1 Handoff Summary — Members 1 and 2

## Completed work

**Member 1 — data and features:** Dataset analysis, EDA, data dictionary, preparation methodology, and the historical feature pipeline are documented. The supplied daily CSV has 8,936 rows and 16 columns (2022-01-01 to 2024-08-09). The isolated feature run produced 8,936 rows and 12 columns with no missing values; its `Traffic Volume` target was numeric, finite, nonnegative, and ranged from 4,233 to 72,039. The external source listing was not independently verified, and the dataset license remains **unverified**.

**Member 2 — daily traffic-volume baseline:** The adopted local feature and training implementation was reproduced in a separate scratch workspace using Python 3.12.6 and scikit-learn 1.7.2. Its local baseline report records Python 3.14.0 and scikit-learn 1.8.0. The pre-adoption GitHub clone used a different pipeline and reported different metrics; the scratch run does not reproduce that legacy baseline. The adopted local chronological split trained on 7,145 rows / 761 dates from 2022-01-01 to 2024-01-31 and tested on 1,791 rows / 191 dates from 2024-02-01 to 2024-08-09. Scratch metrics matched the adopted local implementation's report at displayed precision:

| Model | RMSE | MAE | R² |
|---|---:|---:|---:|
| Mean baseline | 12846.2 | 10544.0 | -0.000 |
| Linear Regression | 10454.1 | 8499.3 | 0.338 |
| Random Forest | 10965.4 | 8808.5 | 0.271 |
| XGBoost | 10964.8 | 8831.6 | 0.271 |

The target is same-day daily `Traffic Volume`; its unit is unspecified. It is not a queue-length target and does not predict five minutes ahead. The trainer uses the chronological test split to select the lowest-RMSE model, so future model selection needs a separate validation set and an untouched final test set.

## Files for team handoff

- Reports and plans: `docs/data_dictionary.md`, `docs/data_preparation_methodology.md`, `docs/member1_phase1_report.md`, `docs/member2_phase1_report.md`, `docs/model_results.md`, `docs/sumo_data_specification.md`, `docs/queue_prediction_evaluation_plan.md`, and `docs/phase1_reproduction_guide.md`.
- EDA: `notebooks/eda.py`, `notebooks/eda_findings.md`, `notebooks/eda_summary.txt`, and six `notebooks/plot_*.png` outputs.
- Pipeline and focused tests: `src/features/build_features.py`, `src/features/bangalore_events.csv`, `src/models/train.py`, `tests/test_features.py`, and `tests/test_train.py`.

The scratch reproduction workspace is outside the project folder at `../phase1-baseline-repro/project`; its generated report and environment are evidence, not part of the proposed repository file set. Do not add the virtual environment, raw/processed CSVs, model files, `mlflow.db`, or `mlruns/` blindly. The raw CSV is DVC-managed and the license is unverified; follow the repository owner's data-sharing policy. The generated `notebooks/profile_report.html` is about 1.34 MB, is not referenced by the Phase 1 reports, and its generator `notebooks/profile_report.py` requires `ydata-profiling`, which is not in the pinned requirements; include it only if the team explicitly wants that optional generated report.

## Remaining ownership and caveats

- The historical Phase 1 deliverables are separate from the implemented Phase 2 SUMO system. See `docs/phase2_handoff_summary.md` for the current 60-second queue model, controller evaluation, CI, DVC, and deployment status.
- DVC pipeline reconciliation remains required before relying on DVC for reproducible runs. The clone's `src/features/bangalore_events.csv` is unchanged, and its MD5 (`5009a60286d1d2f1cbaf812cef418378`) matches the event hash recorded in `dvc.lock`. The adopted `src/features/build_features.py` and `src/models/train.py` MD5 hashes also match the versions recorded in the lock (`a507d3d41aca5a532b44cc74af6039cc` and `41de2b7d96a15c5453e392db9afdcacb`, respectively). The lock records generated `data/processed/traffic_features.csv` and `model.pkl` outputs, which are excluded from this contribution. `dvc.yaml` and `dvc.lock` were intentionally left unchanged; their outputs and stages must be reconciled with the current project before depending on the pipeline.
- The original local project folder remains separate from the existing GitHub clone. No DVC remote was contacted and no push was performed. The original local `model.pkl` was not loaded or verified as working.
- Five focused unit tests passed in an isolated test-only copy with Python 3.12.6: three feature-pipeline tests and two training-helper tests. They do not cover full dataset processing, model training, model artifact loading, MLflow, or SUMO. No coverage percentage is available.

