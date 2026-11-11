# Member 1 — Phase 1 Report

## Verified current-data work

The supplied local historical CSV contains 8,936 rows and 16 columns dated 2022-01-01 through 2024-08-09. Its local contents and DVC-pointer hash were checked, but the original external listing was not independently verified. Dataset license status remains **unverified**.

The feature pipeline's isolated scratch reproduction produced 8,936 rows and 12 columns. All processed columns had zero missing values; `Traffic Volume` was numeric, finite, nonnegative, and ranged from 4,233 to 72,039. The output retains all 24 IQR-flagged observations. It contains daily calendar/context features and text category labels, with `Traffic Volume` as the existing same-day regression target.

The EDA, data dictionary, and preparation methodology describe the current dataset and its limitations. For reproduction, the original raw CSV was copied byte-for-byte into the separate `phase1-baseline-repro` scratch workspace and used as an input. Feature generation created the processed CSV there; training created the model, generated report, and MLflow history there. The original processed CSV, model, report, dependency files, and MLflow history were not used as outputs or overwritten. The adopted local feature and training implementation was successfully reproduced in that scratch workspace using Python 3.12.6 and scikit-learn 1.7.2. This was not a reproduction of the different pre-adoption GitHub-clone pipeline.

## Phase 2 relationship

Phase 1 used the historical daily traffic-volume dataset only. The separate Phase 2 SUMO collector, 60-second queue labeler/model, controller experiments, API, and MLOps work are documented in `docs/sumo_data_specification.md`, `docs/queue_prediction_evaluation_plan.md`, and `docs/phase2_handoff_summary.md`. Phase 1 metrics are not queue-prediction metrics.

## Member 1 Phase 1 files

- `docs/data_dictionary.md` — raw field descriptions and prepared-data interface.
- `docs/data_preparation_methodology.md` — validation, transformations, exclusions, and verified scratch-output checks.
- `notebooks/eda.py`, `notebooks/eda_summary.txt`, and `notebooks/eda_findings.md` — EDA procedure, recorded findings, and interpretation limits.
- `src/features/build_features.py` — current historical feature-generation pipeline.
- `docs/sumo_data_specification.md` — implemented Phase 2 SUMO observation/label contract for the separate 60-second queue model.

Member 2's Phase 1 documentation is recorded separately in `docs/member2_phase1_report.md` and `docs/queue_prediction_evaluation_plan.md`.
