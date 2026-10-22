# Member 1 — Phase 1 Report

## Verified current-data work

The supplied local historical CSV contains 8,936 rows and 16 columns dated 2022-01-01 through 2024-08-09. Its local contents and DVC-pointer hash were checked, but the original external listing was not independently verified. Dataset license status remains **unverified**.

The feature pipeline's isolated scratch reproduction produced 8,936 rows and 12 columns. All processed columns had zero missing values; `Traffic Volume` was numeric, finite, nonnegative, and ranged from 4,233 to 72,039. The output retains all 24 IQR-flagged observations. It contains daily calendar/context features and text category labels, with `Traffic Volume` as the existing same-day regression target.

The EDA, data dictionary, and preparation methodology describe the current dataset and its limitations. For reproduction, the original raw CSV was copied byte-for-byte into the separate `phase1-baseline-repro` scratch workspace and used as an input. Feature generation created the processed CSV there; training created the model, generated report, and MLflow history there. The original processed CSV, model, report, dependency files, and MLflow history were not used as outputs or overwritten. The adopted local feature and training implementation was successfully reproduced in that scratch workspace using Python 3.12.6 and scikit-learn 1.7.2. This was not a reproduction of the different pre-adoption GitHub-clone pipeline.

## Limits and future SUMO dependency

The historical dataset has no time-of-day, queue-length, signal-state, or future queue label. It cannot support five-minute queue prediction. The proposed SUMO data schema is future work; SUMO collection and queue prediction are **not implemented**.

Member 3's future implementation must confirm the network topology and identifiers, queue measurement method and location, sampling interval, signal-state fields, run metadata, and separate storage format. Member 1 can validate and document simulated observations after those decisions and a sample output are available. Simulated data must remain separate from the historical daily traffic-volume dataset. Member 3 owns the assigned Git/DVC and SUMO infrastructure implementation; this report does not imply that the SUMO infrastructure already exists. Members 1 and 2 are completing their respective data and model-evaluation deliverables.

## Member 1 Phase 1 files

- `docs/data_dictionary.md` — raw field descriptions and prepared-data interface.
- `docs/data_preparation_methodology.md` — validation, transformations, exclusions, and verified scratch-output checks.
- `notebooks/eda.py`, `notebooks/eda_summary.txt`, and `notebooks/eda_findings.md` — EDA procedure, recorded findings, and interpretation limits.
- `src/features/build_features.py` — current historical feature-generation pipeline.
- `docs/sumo_data_specification.md` — proposed future simulation schema and leakage controls; not an implemented collector.

Member 2's Phase 1 documentation is recorded separately in `docs/member2_phase1_report.md` and `docs/queue_prediction_evaluation_plan.md`.
