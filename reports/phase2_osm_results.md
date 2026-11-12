# Current Phase 2 Results and Limitations

## Scope

This report summarizes the latest OSM-corridor queue-model evaluation and available controller experiments in the supplied project archive. Older synthetic-grid, P10/P50/P90, 300-second, and earlier 60-second results are historical experiments and are not substituted for the current Bengaluru OSM model. The Phase 1 daily `Traffic Volume` model is a separate task; its documented unit is unspecified. The historical dataset license remains **unverified**.

The OSM road geography comes from OpenStreetMap. Traffic demand, vehicle composition, SUMO behavior, converted signal plans, and simulation results are synthetic/assumed. The work is not a calibrated or field-validated Bengaluru digital twin.

## Current queue model

The model target is `queue_length_m_t_plus_60s`: the contiguous stopped-vehicle queue measured 60 seconds later on the same run, intersection, and lane. Vehicles are considered stopped at speed <=0.1 m/s and join the contiguous queue when bumper gap <=2.5 m; the reported physical length includes vehicle bodies and gaps. This is a simulation measurement, not field ground truth.

The 11 model inputs are current queue length, vehicle count, halting-vehicle count, mean speed, signal phase elapsed time, intersection ID, approach ID, lane ID, signal phase ID, signal state, and assumed vehicle composition. Training/validation/test partitions use complete simulation seeds: train 7/42/2026 (185,896 rows), validation 99 (59,052), test 123/31415 (112,176). No seed crosses partitions. Preprocessing is fit on training data only. The decision threshold is selected on validation data. The evaluator also checks the held-out test against predeclared persistence quality gates; do not use these test results to tune a future model or threshold.

| Held-out test metric | Model | Persistence (predict current queue) |
|---|---:|---:|
| Rows | 112,176 | same 112,176 |
| MAE | 0.055003 m | 0.069353 m |
| RMSE | 0.513549 m | 0.651288 m |
| R² | 0.883569 | 0.812737 |

On the positive future-queue subset (2,753 rows), model MAE is 2.199547 m, RMSE 3.236860 m and R² 0.667340. The overall score is influenced by many zero-queue cases. These results are simulation-domain estimates only; they do not establish real-world queue accuracy.

Persistence on the same subsets (recomputed 2026-11-12 from the identical 112,176 test rows; see `reports/phase2_verification_20261112.md`):

| Test subset | Rows | Model MAE / RMSE | Persistence MAE / RMSE |
|---|---:|---:|---:|
| All rows | 112,176 | 0.0550 / 0.5135 m | 0.0694 / 0.6513 m |
| Future queue > 0 | 2,753 | 2.1995 / 3.2369 m | **1.9020** / 3.4377 m |
| Current or future queue > 0 | 3,357 | **1.8321** / 2.9620 m | 2.3175 / 3.7648 m |
| Future queue = 0 | 109,423 | **0.0010** / 0.0823 m | 0.0232 / 0.3708 m |

On rows whose future queue is positive, the model's MAE is worse than persistence (+15.6 %); its RMSE is better (−5.8 %) and its R² is higher (0.667 vs 0.625). Most of the aggregate improvement comes from rows whose queue clears within 60 s. Do not quote a positive-subset MAE improvement over persistence.

The API metadata now names the Metaflow run `1794405200312669` artifact, SHA-256 `167b523fc8c89199f6a8bf0689475272654db96b59b8a1da9b8a9986bff0b13b`. It was reproduced byte-for-byte by a fresh run (`1794473115185929`) on 2026-11-12. The earlier deployment candidate `models/bengaluru/bengaluru_queue_hurdle_v1_2026-11.joblib`, SHA-256 `72bc01ba9b659eeb47cd977b9bfb691e552da9f610bf637a96b05d3d36f9ea71`, is a separately serialized file. When both were loaded with scikit-learn 1.7.2, their predictions on all 112,176 test rows differed by at most 7.1e-15 m, but they are not interchangeable for SHA-256 pinning. The selected deployment candidate was freshly loaded by the local Docker API smoke test; the original Phase 1 `model.pkl` was not loaded or verified as a working model.

## Controller experiments

The current OSM experiment ledger is quality-marked. Low-demand fixed/adaptive/predictive runs have three paired seeds and no quality failures. Mean travel times were 504.08 s fixed, 507.61 s adaptive, and 507.27 s predictive. Predictive was not better than fixed on this mean. Medium runs have three paired seeds, but two pairs contain teleports; high runs have teleports/collisions and an incomplete predictive matrix. Those runs are not clean evidence for a policy winner. In the separate medium-300 batch, all nine runs were clean (three policies x three seeds); mean travel time was 531.30 s fixed, 536.10 s adaptive, 536.74 s predictive, with zero teleports/collisions. That batch also does not show predictive superiority.

The retained older synthetic-grid P25 comparison is a separate experiment and must not be conflated with the OSM-corridor results. In that matrix all 27 rows share route/network hashes within scenario/seed pairs; its metrics are reported in `docs/phase2_perimeter_experiment_report.md`.

## Metaflow, API and test evidence

Metaflow run `1794370252312711` records an earlier training/evaluation with dataset hash, complete-seed partitions, model hash, and metrics. Fresh runs `1794391865386585`, `1794393031537675`, and the latest `1794405200312669` were executed on 2026-11-11 via WSL using Python 3.12.3, Metaflow 2.19.41, NumPy 2.2.6, pandas 2.3.3, scikit-learn 1.7.2, and joblib 1.6.0. They processed the same 357,124-row dataset (SHA-256 `4e8213df71d3ed2df8bb2995ec195e1610f4398ad37f0e049a4399d9f93a5ffb`), preserved the seed split, and reproduced the test metrics. The fresh Metaflow model SHA-256 is `167b523fc8c89199f6a8bf0689475272654db96b59b8a1da9b8a9986bff0b13b`. The latest run stores its model bytes and record in Metaflow artifacts; the local registry checker verified and exported it with the same hash. This is a local registry, not a shared hosted service. The API deployment candidate is a distinct artifact and was independently loaded by a local Docker smoke test.

The FastAPI service was started locally against the deployment-candidate model: health returned `ok`, model-info returned the expected target/horizon/hash, and a valid request returned a finite nonnegative prediction. The focused unit suite is `unittest`, not pytest. See the audit report for exact results and remaining clean-checkout limitations.

## Limitations and next work

- The OSM-derived network and assumed SUMO inputs are not field-calibrated.
- Synthetic traffic/fleet assumptions are not measured Bengaluru data. Historical daily volume is not an arrival profile.
- Queue data are sparse in the positive-target region; report both all-row and positive-only metrics.
- Controller evaluations with teleports/collisions are quality failures; predictive control is not shown to be superior.
- Docker image build and local container API smoke checks passed on 2026-11-11 with the `72bc…` artifact; no image was published. The `167b` artifact was verified through the API and the image entrypoint on 2026-11-12, but not inside a built container.
- GitHub Actions run `43036696130` passed on branch `phase2-completion-20261111` at commit `a85972c`; deploy was skipped. On `main` at `d858900`, push run `43039410684` passed (deploy skipped). Manual run `43060494475` passed checks, and its deploy job succeeded (the Render deploy hook was accepted and `/health` returned 200 inside CI). Hosted `/predict` has not been verified.
- Local `dvc status` on the handover checkout reports the Phase 1 raw/processed files, `model.pkl`, and OSM/network payloads missing from local cache. No remote status, pull, or push was performed. DVC remote access and lock reconciliation remain unverified; no teammate ownership is assumed. See `reports/phase2_verification_20261111.md`.
- No hosted model registry, public deployment, production feedback pipeline, or live-signal integration is established.
- The dataset license remains unverified.
