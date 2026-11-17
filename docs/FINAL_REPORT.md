# Final Report: AI-Driven Adaptive Traffic Management Using a Digital Twin

Course: Machine Learning Operations (AI252TA), Tutorials 2026-27. Date: 2026-11-16.
Repository: `PriyankaSrvce/traffic-mlops`. Live service: https://traffic-queue-api.onrender.com

This report maps the project to the complete MLOps lifecycle required by the course circular.
Every number comes from a file in this repository; the file is named next to it.

---

## 1. Problem and ML model

**Problem.** Fixed-time traffic signals cannot react to queues that are about to form. If the
queue on each lane can be predicted a short time ahead, a signal controller can act before the
queue builds.

**ML task.** Regression: predict the queue length (metres) on one lane **60 seconds ahead** from
the lane's current state (queue, vehicle counts, mean speed, signal phase and timing, location,
vehicle mix).

**Data.** A digital twin: SUMO simulations on a road network converted from OpenStreetMap for a
Bengaluru corridor with 35 signalised junctions. Demand levels and vehicle mixes are documented
assumptions, not field counts.

**Model.** A hurdle model: a Random Forest classifier decides whether a queue will exist, and a
Random Forest regressor predicts its length. About 97.5 % of observations have no queue, and a
single regressor failed the quality gate.

**Two separate tasks.** Phase 1 used a historical Bangalore CSV to build a daily traffic-volume
baseline. Phase 2 and 3 use the SUMO queue model. The two are never mixed.

## 2. MLOps lifecycle coverage

| Lifecycle stage (circular) | What was done | Tools | Evidence |
|---|---|---|---|
| Data exploration | EDA of the historical dataset; dataset validation of every SUMO run | pandas, matplotlib | `notebooks/eda.py`, `docs/data_dictionary.md`, `aggregate_dataset.py` |
| Feature engineering | Calendar and event features (Phase 1); lane-state features and +60 s labels (Phase 2) | pandas | `src/features/build_features.py`, `label_observations.py` |
| Experimentation and evaluation | Baselines vs models with a time-aware split (Phase 1); persistence baseline vs candidates with a whole-seed split (Phase 2) | MLflow (Phase 1 tracking), Metaflow (Phase 2/3 runs) | `docs/model_results.md`, `reports/phase2_osm_results.md` |
| Version management and reproducibility | Git; DVC for data; pinned requirements; model identity = SHA-256; bit-for-bit reproduction of the model | Git, DVC, Metaflow | `*.dvc`, `data/sumo/README.md`, `registry/model_versions.json` |
| QA / testing | 60 automated tests run in CI | PyTest, GitHub Actions | `tests/`, `.github/workflows/phase2-ci.yml` |
| Model risk and security | Hash check before unpickling; non-root container; secrets outside git; strict input validation | FastAPI/pydantic, Docker | `src/api/app.py`, `Dockerfile`, `docs/GOVERNANCE.md` §3, §7 |
| Model registry | Append-only registry of every version with stage, lineage and reason | Metaflow artifacts + JSON registry | `registry/model_versions.json`, `scripts/model_promotion.py` |
| Containerization | API image that downloads and verifies the pinned model | Docker | `Dockerfile`, `docker_entrypoint.py` |
| CI/CD | Tests, Metaflow graph checks, image build and smoke test on every push/PR; manual deploy job | GitHub Actions | `.github/workflows/phase2-ci.yml` |
| Deployment | Public prediction service | Render | `/api/v1/health`, `/api/v1/model-info`, `/docs` |
| Monitoring / logging | Drift reports, per-prediction logs, live metrics and dashboards | Evidently, Python logging, Prometheus, Grafana | §5 below |
| Drift detection | Induced demand-surge and sensor-fault drift, detected by two tools | Evidently, PSI detector | `reports/phase3_drift/` |
| Feedback / retraining | Ground-truth feedback endpoint; automatic trigger; retrained v2; v1-vs-v2 comparison | Metaflow | `scripts/retraining_trigger.py`, `promotion_comparison.json` |
| Governance | Roles, gates, policies, audit trail, model card | – | `docs/GOVERNANCE.md`, `docs/MODEL_CARD.md` |

## 3. Phase 1: development and reproducibility

- **Dataset.** Historical Bangalore traffic CSV: 8,936 rows, 16 columns, 2022-01-01 to 2024-08-09. Tracked with DVC (`data/raw/bangalore_traffic.csv.dvc`). Its licence is unverified and its traffic-volume unit is unspecified; both are stated in the docs.
- **Features.** 12 columns after preparation, no missing values (`src/features/build_features.py`).
- **Baselines** (time-aware split, test from 2024-02-01; `docs/model_results.md`):

| Model | RMSE | MAE | R² |
|---|---:|---:|---:|
| Mean baseline | 12846.2 | 10544.0 | −0.000 |
| Linear Regression | 10454.1 | 8499.3 | 0.338 |
| Random Forest | 10965.4 | 8808.5 | 0.271 |
| XGBoost | 10964.8 | 8831.6 | 0.271 |

- **Tracking.** MLflow logs parameters and metrics for these runs (`src/models/train.py`); the DVC pipeline (`dvc.yaml`) has the `featurize` and `train` stages.
- **Finding.** Daily volume is only weakly predictable (best R² 0.338), and a daily value cannot drive a signal. This motivated the move to a simulation with a short-horizon target.

## 4. Phase 2: productionization and deployment

- **Digital twin and data.** 18 SUMO runs (low / medium / high demand, two vehicle mixes, six seeds) gave 357,124 labelled rows after incident quarantine.
- **Model result** (112,176 held-out test rows; `reports/phase2_verification_20261112.md`):

| Predictor | MAE (m) | RMSE (m) | R² |
|---|---:|---:|---:|
| Persistence baseline | 0.0694 | 0.6513 | 0.8127 |
| Hurdle model v1 (`167b523f…`) | 0.0550 | 0.5135 | 0.8836 |

  The model's MAE is 21 % lower overall. On the 2,753 rows where a queue will exist, persistence has the lower MAE (1.90 vs 2.20 m); this weakness is disclosed in the model card.
- **Quality gate.** The Metaflow `acceptance` step stops the flow unless MAE is at least 5 % better than persistence and RMSE is no worse, on both validation and test.
- **Testing.** PyTest suite, run on every push and pull request.
- **Serving.** FastAPI: `/predict`, `/model-info`, `/health`. The API refuses to start if the model's SHA-256 does not match the approved value.
- **Container and CI/CD.** Docker image (non-root user, health check). GitHub Actions job `checks-and-image` runs on every push/PR; the `deploy` job runs only on manual dispatch on `main`.
- **Deployment.** Render serves the model. In Phase 2, `/api/v1/model-info` reported SHA `167b523f…` (v1); since 2026-11-17 it reports `8da60b0e…` (v2, §5.4).
- **Controller experiment.** Fixed-time, adaptive and predictive signal control were compared in SUMO. Fixed-time had the lowest mean travel time in the clean runs. The project therefore does **not** claim that predictive control is better; the contribution is the prediction service and its MLOps pipeline.

## 5. Phase 3: monitoring, feedback and governance

### 5.1 Simulated production data and induced drift

| Batch | How it was made | Rows |
|---|---|---:|
| Normal (control) | Held-out test seeds | 112,176 |
| Normal, balanced mix (matched control) | Held-out validation seed, same vehicle mix as the surge runs | 59,052 |
| Surge 600 veh/h | New SUMO runs, demand 11 % above the training maximum | 55,556 |
| Surge 720 veh/h | New SUMO runs, severe surge | 63,688 |
| Sensor fault | Test batch with speed reported in km/h instead of m/s (synthetic, tagged) | 112,176 |

### 5.2 Drift detection results

PSI detector (`reports/phase3_drift/drift_report.json`):

| Batch | Worst PSI | MAE (m) | vs approved 0.0550 | Action |
|---|---:|---:|---:|---|
| Normal | 0.014 | 0.0550 | 0 % | No action |
| Normal, balanced mix | 0.053 | 0.0513 | −7 % | No action |
| Surge 600 | 0.123 | 0.0877 | +59 % | Retraining recommended |
| Surge 720 | 0.168 | 0.0769 | +40 % | Retraining recommended |
| Sensor fault | 0.765 | 0.0556 | +1 % | Investigate data pipeline |

Evidently 0.7.23 (`reports/phase3_drift/evidently_summary.json`; Wasserstein distance, drift at ≥ 0.1; reference and batches compared on the same vehicle mix):

| Batch | Drifted columns, all rows | Drifted columns, occupied lanes (largest score) |
|---|---|---|
| Normal, balanced mix | none (max 0.011) | none (max 0.094) |
| Surge 600 | none (max 0.061) | queue, vehicle count, halting count (0.172) |
| Surge 720 | none (max 0.072) | queue, vehicle count, halting count (0.224) |
| Sensor fault | speed (0.254) | speed (1.482) |

The two tools agree. Three findings matter:

1. **Zero-inflated data hides drift.** With 97.5 % empty lanes, the original PSI function gave 0.000 for every feature, even for the sensor fault. It was fixed, and both tools are also run on occupied lanes, where the surge is visible.
2. **Not every drift means retraining.** The sensor fault changes the inputs sharply but barely changes accuracy. The policy sends it to a pipeline investigation; retraining would teach the model the fault.
3. **Compare like with like.** Evidently first reported drift on normal data because the reference and the batch had different vehicle mixes. A matched control removed this false alarm.

### 5.3 Logging, metrics and dashboards

- **Python logging.** One structured line per prediction, feedback record, rejected model file and failed prediction (`src/api/app.py`).
- **Prometheus.** `/metrics` exposes request counts, latency, input and prediction distributions, feedback error, model identity and the last drift report.
- **Grafana.** `monitoring/docker-compose.yml` starts the API, Prometheus and a provisioned dashboard. `scripts/replay_production_traffic.py` replays normal traffic, then a surge, then the sensor fault. In the recorded replay (600 occupied-lane rows per phase) the live MAE rose from 0.83 m to 1.34 m under the surge, and the mean input speed roughly tripled under the sensor fault.
- **Web dashboard.** `/dashboard` on the deployed API shows the whole pipeline, drift results, versions, CI runs and governance in one page.

### 5.4 Retraining trigger, retraining and model comparison

1. `scripts/retraining_trigger.py` read the drift report, decided `TRIGGER_RETRAINING` for the two surge batches (and "no retraining" for the sensor fault), and launched the Metaflow flow (`reports/phase3_drift/retraining_request.json`).
2. The flow trained on the v1 data plus 12 new surge runs (607,924 rows) and passed the quality gate. The resulting model `8da60b0e…` was produced identically by three separate runs (Metaflow runs 3, 4 and 5).
3. Comparison on identical rows (`reports/phase3_drift/promotion_comparison.json`):

| Evaluation set | Persistence | v1 | v2 |
|---|---:|---:|---:|
| Original test (normal demand) | 0.0694 | 0.0550 | 0.0527 |
| Surge test seeds | 0.0759 | 0.0901 | 0.0601 |
| Unseen surge 600 | 0.0992 | 0.0877 | 0.0758 |
| Unseen surge 720 | 0.1011 | 0.0769 | 0.0761 |

v2 fixes the drift without regressing on normal traffic. On the unseen 720 veh/h batch the gain is small (1 %).

4. **Redeployment.** After human approval (governance gate P4), v2 was deployed on 2026-11-17: the artifact was published at tag `model-8da6`, the pinned SHA-256 was changed in the code and in Render, and the manual deploy job (CI run #25) was run. The live API reports `8da60b0e…` and matches the offline model on 120 held-out rows (max difference 1.1e-14 m). v1 is archived as the rollback target.
5. **Check after redeployment** (`reports/phase3_drift/drift_report_post_v2.json`). With v2, the model's error as a share of the baseline's error is about 0.76 in normal traffic and in both surges (v1 had slipped to 0.88 on surge 600). The surge batches still exceed the "+25 % vs approved MAE" line (+36 %), because surge traffic is harder for every predictor. The alert is left visible and the rule is recorded for review (`docs/GOVERNANCE.md` §5.3).

### 5.5 Governance

`docs/GOVERNANCE.md` defines roles, data and model controls, the promotion gates, the monitoring policy, change management, responsible-use limits and the audit trail, each with its justification. `docs/MODEL_CARD.md` describes both model versions and their known weaknesses.

## 6. Expected outcomes checklist

| Expected outcome | Status | Evidence |
|---|---|---|
| Versioned dataset in DVC | Done for the Phase 1 CSV and the OSM/network files. Phase 2/3 SUMO datasets have DVC pointer files; their upload to the team's DVC remote must be run by a team member with access | `*.dvc`, `data/sumo/` |
| Experiment history and registered model | Done | MLflow (Phase 1), Metaflow runs, `registry/model_versions.json` |
| Automated tests | Done (60 tests) | `tests/`, CI |
| Dockerized inference API | Done | `Dockerfile` |
| GitHub Actions CI/CD workflow | Done | `.github/workflows/phase2-ci.yml` |
| Deployed prediction service | Done | Render URL above |
| Monitoring / observability dashboard | Done | Grafana (`monitoring/`), `/dashboard`, Evidently reports |
| Deliberately introduced drift scenario | Done | §5.1 |
| Drift detection and retraining / redeployment evidence | Done: drift detected, retraining triggered, v2 compared with v1, v2 redeployed and verified live | §5.2, §5.4, `retraining_request.json`, `registry/model_versions.json` |
| Model card / governance and limitations report | Done | `docs/MODEL_CARD.md`, `docs/GOVERNANCE.md`, §7 |

## 7. Tool choices (hybrid MLOps stack)

| Need | Tool | Why |
|---|---|---|
| Data versioning | DVC | Large files stay out of Git but remain tied to commits |
| Experiment tracking (Phase 1) | MLflow | Quick comparison of several model types |
| Training workflow and artifacts (Phase 2/3) | Metaflow | Each step's inputs and outputs are stored per run, so a model can be traced to its data and reproduced |
| Model registry | SHA-256 registry on top of Metaflow artifacts | The serving API checks the exact file hash, so the registry must be keyed by that hash; stages and reasons are kept in one reviewable file |
| Testing | PyTest | Standard, runs in CI |
| Serving | FastAPI | Typed request validation and automatic API docs |
| Packaging and deployment | Docker, Render | Same image locally, in CI and in production |
| CI/CD | GitHub Actions | Runs on every push; deploy is a separate manual job |
| Drift reports | Evidently | Standard drift tests and visual reports |
| Metrics and dashboard | Prometheus, Grafana | Live service and model monitoring |

## 8. Limitations

- All traffic is simulated; demand and vehicle mix are assumptions. Nothing is validated on field data.
- Drift batches are simulated scenarios and one synthetic fault, replayed as "production" traffic.
- Grafana and Prometheus run locally with Docker; the free hosting plan serves only the API.
- The feedback endpoint is unauthenticated (demo use only).
- Better prediction did not translate into better signal control in the verified experiments.

## 9. Demonstration order

1. Live web dashboard: https://traffic-queue-api.onrender.com/dashboard (pipeline, drift, versions, CI, governance).
2. Evidently reports, opened from the dashboard's drift section.
3. Grafana: `monitoring/docker-compose.yml`, then `scripts/replay_production_traffic.py` to watch normal → surge → sensor fault.
4. Metaflow UI: run 2 (v1) and runs 3–5 (v2, including the trigger-launched runs). `/api/v1/model-info` shows v2 live.
5. GitHub Actions: test, build and deploy jobs.
