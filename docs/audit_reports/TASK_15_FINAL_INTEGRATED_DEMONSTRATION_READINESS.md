# TASK 15 — Phase 2 Final Integrated Demonstration Readiness

**Authoritative Repository:** `D:\TrafficMLOps_Phase2_Workspace\repository`  
**Inspected Branch & Commit:** `main` @ `d85890058a13094ab3852f6297d87f29d5d01d0e`  
**Audit Protocol:** Strictly read-only; no modifications to repository files, no test executions that mutate disk, no remote calls, and zero fabrication of unverified functionality.

---

## 1. Objective and Audit Scope

This report establishes the final, integrated demonstration plan and technical viva defense dossier for Phase 2 of the AI-Driven Adaptive Traffic Management project. It consolidates all findings, evidence, metrics, and forensic audits established across Tasks A through B2 and Tasks 1 through 14.

### Scope of Integration:
* Accurate reconciliation of the end-to-end data, simulation, training, serving, and monitoring lifecycle.
* Step-by-step demonstration walkthrough distinguishing runnable code from archived evidence.
* Strict classification of verified execution, unit test verification, archived proofs, and blocked functions.
* Master viva question-and-answer catalog addressing all 13 core evaluation topics.
* Complete disclosure of all 7 unresolved physical asset and documentation discrepancies.
* Final demonstration readiness classification (READY, PARTIALLY READY, BLOCKED).

---

## 2. Final Architecture Reconciliation

The end-to-end Phase 2 technical architecture consists of 10 sequential stages. Rather than an idealized linear pipeline, the actual codebase connects components as follows:

```
[1. OpenStreetMap Extract]
       | (WGS84 bounds: 77.567,12.882,77.693,12.958)
       v
[2. SUMO Left-Hand Network Conversion]
       | (netconvert --lefthand --tls.guess-signals --tls.join -> bengaluru_osm_sim.net.xml)
       v
[3. Microscopic Corridor Simulation]
       | (generate_scenario.py & demo.sumocfg: 3 anchors [Silk Board, HSR, Koramangala],
       |  6 OD paths, 5 vehicle archetypes [vtypes.add.xml], 2 fleet profiles, 3 demand levels)
       v
[4. Contiguous Queue Measurement & Forward Labeling]
       | (queue_measurement.py: speed <= 0.1 m/s, gap <= 2.5 m)
       | (label_observations.py: exact lane join at t + 60s -> target: queue_length_m_t_plus_60s)
       | (aggregate_dataset.py: incident quarantine -> training_labels_incident_quarantined.csv, 357k rows)
       v
[5. Metaflow Pipeline Orchestration]
       | (flows/bengaluru_queue_model_flow.py: start -> train_evaluate -> acceptance -> end)
       | (Seed-isolated splits: train [7,42,2026], val [99], test [123,31415])
       v
[6. Two-Stage Hurdle Model Engine]
       | (evaluate_hurdle.py & bengaluru_model.py)
       | Stage 1: Balanced Random Forest Classifier (predicts probability of queue > 0)
       | Stage 2: Conditional Random Forest Regressor (predicts continuous queue magnitude in metres)
       | Validation Tuning: Optimal decision threshold selected on validation seed 99
       v
[7. Model Registry Acceptance & Packaging]
       | (scripts/model_registry_report.py: validates run success, target, horizon, and SHA-256)
       | Enforces 5% MAE improvement over persistence baseline; exports verified .joblib binary
       v
[8. FastAPI Real-Time Serving]
       | (src/api/app.py: dual routes /health, /model-info, /predict under / and /api/v1/)
       | Pre-deserialization SHA-256 HMAC validation before joblib.load; Pydantic v2 schemas; HTTP 503 fallback
       v
[9. Docker Containerization & CI/CD Gating]
       | (Dockerfile & docker_entrypoint.py: non-root apiuser, allowlist .dockerignore)
       | (.github/workflows/phase2-ci.yml: 34 unit tests, compile, DAG check, Docker build, gated deploy)
       | (render.yaml: autoDeploy off, deploy webhook, health check /health)
       v
[10. Offline Performance Monitoring & Feedback Ledger]
       (monitoring.py: quantile-binned PSI for feature drift, stratified MAE/RMSE/R2)
       (record_feedback.py: 8-key exact join, immutable ledger, anti-leakage retraining guards)
```

### Architectural Realities & Missing Links:
* **Simulation to Training:** The simulation outputs are aggregated into CSVs, but this is an offline batch file transfer, not an automated streaming pipeline.
* **DVC Disconnect:** The Phase 2 dataset (357k rows) is **not** managed by DVC; DVC tracks only Phase 1 historical data and raw OSM geometry XML files.
* **API to Monitoring:** Live API requests are **not** logged to a database or Kafka topic; the monitoring script operates exclusively on held-out simulation test batches.

---

## 3. Demonstration Sequence & Execution Playbook

This playbook outlines the exact 7-step sequence to present live to evaluators, clearly stating what runs, what commands to use, and where missing assets apply:

### Step 1: Git Branch Authority and Working Tree Cleanliness
* **What to Show:** Project root Git status and commit history.
* **Exact Command:**
  ```powershell
  git status
  git log -n 3 --oneline
  ```
* **Expected Result:**
  * Branch: `main`
  * Head Commit: `d858900`
  * State: `nothing to commit, working tree clean`
* **Execution Status:** **READY TODAY** (Can be executed immediately; requires zero external assets).

### Step 2: Complete Hermetic Unit Test Suite
* **What to Show:** Execution of all 34 unit tests across 7 test modules.
* **Exact Command:**
  ```powershell
  python -m unittest discover -s tests -v
  ```
* **Expected Result:**
  * Discovers: `test_api.py` (10), `test_bengaluru_monitoring.py` (3), `test_bengaluru_scenario.py` (6), `test_features.py` (3), `test_model_registry.py` (4), `test_perimeter_routes.py` (6), `test_train.py` (2).
  * Outcome: `Ran 34 tests in ~0.15s` $\rightarrow$ `OK`.
* **Execution Status:** **READY TODAY** (100% hermetic unit tests; all fixtures are synthetic; zero external dependencies).

### Step 3: Metaflow Workflow DAG Static Verification
* **What to Show:** DAG structure, parameter contracts, and seed split declarations.
* **Exact Command:**
  ```powershell
  python flows/bengaluru_queue_model_flow.py --metadata=local --datastore=local check
  ```
* **Expected Result:** `Flow BengaluruQueueModelFlow is valid.`
* **Execution Status:** **READY TODAY** (Validates workflow syntax and DAG connectivity statically).
* *Caveat:* Full execution (`run`) is **BLOCKED** because the 105 MB training dataset `training_labels_incident_quarantined.csv` is absent from disk.

### Step 4: API Defense-in-Depth, Schema Validation, and Safe Degradation
* **What to Show:** Launching the API without model weights and testing its fail-safe degradation and Pydantic validation.
* **Exact Commands:**
  * Terminal 1 (Start server in degraded mode):
    ```powershell
    python -m uvicorn src.api.app:app --port 8000
    ```
  * Terminal 2 (Probe health check):
    ```powershell
    curl -i http://127.0.0.1:8000/health
    ```
    *Result:* `HTTP/1.1 503 Service Unavailable` with `{"detail": "Validated Bengaluru model artifact is not configured"}`.
  * Terminal 2 (Probe validation defense with negative queue and extra field):
    ```powershell
    curl -i -X POST http://127.0.0.1:8000/predict -H "Content-Type: application/json" -d "{\"queue_length_m\": -5.0, \"unauthorized_field\": 123}"
    ```
    *Result:* `HTTP/1.1 422 Unprocessable Entity` with explicit Pydantic validation errors.
* **Execution Status:** **READY TODAY** (Demonstrates server startup, graceful 503 degradation, and strict input validation without needing model binaries).

### Step 5: Verification of Archived Model Inference Evidence
* **What to Show:** Open and present [`reports/demo_smoke_20261111/heldout_positive_sample_result.json`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/reports/demo_smoke_20261111/heldout_positive_sample_result.json).
* **Expected Result:**
  * Target: `queue_length_m_t_plus_60s` (Horizon: 60s)
  * Observed Ground Truth Queue: **`11.0 m`**
  * Model Predicted Queue: **`5.1656687762301035 m`**
  * Absolute Error: **`5.8343 m`**
  * Model Hash: `72bc01ba9b659eeb47cd977b9bfb691e552da9f610bf637a96b05d3d36f9ea71`
  * Seed: `123`
* **Execution Status:** **ARCHIVED EVIDENCE** (Captured during local Docker container testing on 2026-11-11; live rerunning requires staging the `.joblib` binary).

### Step 6: Empirical Controller Comparison & Teleport Invalidation
* **What to Show:** Display [`reports/phase2_osm_results.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/reports/phase2_osm_results.md) and [`sumo/bengaluru_osm/controller.py`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/sumo/bengaluru_osm/controller.py).
* **Expected Result:**
  * Low Demand (Clean runs): Fixed-Time Mean Travel Time = **504.08s**, Adaptive = **507.61s**, Predictive = **507.27s**.
  * Medium-300 Batch (9 clean runs): Fixed-Time = **531.30s**, Adaptive = **536.10s**, Predictive = **536.74s**.
  * High Demand: Flagged as `quality_failure` due to SUMO vehicle teleports and junction gridlocks.
* **Execution Status:** **ARCHIVED DOCUMENTED EVIDENCE** (Live SUMO simulation rerunning is **BLOCKED** because `bengaluru_osm_sim.net.xml` and SUMO binaries are missing).

### Step 7: GitHub Actions CI/CD Telemetry & Gated Deployment
* **What to Show:** Display GitHub Actions Run telemetry for commit `d858900`.
* **Verified Telemetry:**
  1. [Run `43039410684`](https://github.com/PriyankaSrvce/traffic-mlops/actions/runs/43039410684) (Push on `main`): Passed all compile checks, 34 unit tests, Metaflow DAG checks, and Docker image build (1m 19s). Deploy job skipped.
  2. [Run `43060494475`](https://github.com/PriyankaSrvce/traffic-mlops/actions/runs/43060494475) (Workflow dispatch on `main` with `deploy_production: true`): Passed checks and executed deployment job (37s), receiving HTTP 200 from the Render health check.
* **Execution Status:** **VERIFIED REMOTE CI EVIDENCE** (Verified via GitHub Actions REST API).

---

## 4. Evidence Classification Matrix

To ensure absolute scientific integrity, all project evidence is partitioned into 6 distinct categories:

| Evidence Tier | Component / Asset | Verification Status & Proof |
|---|---|---|
| **Tier 1: Verified Actual Execution** | GitHub Actions CI/CD | Runs `43039410684` and `43060494475` verified live via GitHub API on commit `d858900`. |
| | API Degraded Startup | Uvicorn starts cleanly; `/health` returns HTTP 503; malformed JSON returns HTTP 422. |
| **Tier 2: Unit Test Verification** | Hermetic Test Suite | Exactly 34 tests pass in 0.15s across 7 modules (API, monitoring, scenario, features, registry). |
| | Pre-Deserialization Defense | `test_hash_mismatch_prevents_deserialization` proves `joblib.load` is never called on hash mismatch. |
| **Tier 3: Source Code Verification** | Metaflow Workflow | `flows/bengaluru_queue_model_flow.py` statically verified via Metaflow CLI. |
| | Docker & Security | `Dockerfile` (non-root `apiuser`), allowlist `.dockerignore`, `render.yaml` blueprint. |
| | Queue Definition | Speed $\le 0.1\text{ m/s}$ and contiguity gap $\le 2.5\text{ m}$ verified in `queue_measurement.py`. |
| | Offline Monitoring | Quantile-binned PSI formula and immutable feedback ledger verified in `monitoring.py`. |
| **Tier 4: Archived Execution Evidence** | Single Inference Sample | `reports/demo_smoke_20261111/heldout_positive_sample_result.json` (5.17m predicted vs. 11.0m label). |
| | Model Performance | 0.055m overall MAE ($N=112k$); 2.20m positive MAE ($N=2,753$) documented in `phase2_osm_results.md`. |
| | Controller Results | Low-demand (504s vs. 507s) and medium-300 (531s vs. 536s) documented in `phase2_osm_results.md`. |
| **Tier 5: Blocked Demonstrations** | Live Retraining | Blocked by missing `training_labels_incident_quarantined.csv` (105 MB). |
| | Live Model Serving | Blocked by missing model binaries (`*.joblib`) in the current checkout. |
| | Live SUMO Simulation | Blocked by missing `bengaluru_osm_sim.net.xml` (242 MB) and missing SUMO system binaries. |
| | CLI Monitoring Execution | Blocked by missing train/test split CSVs. |
| **Tier 6: Future Work** | Production Observability | Prometheus exporter (`/metrics`), Grafana dashboards, automated Slack/PagerDuty alerts. |
| | Municipal Integration | Field radar/camera sensor integration and municipal signal controller hardware interfacing. |

---

## 5. Comprehensive Viva Preparation Dossier (Top 13 Technical Questions)

### Q1: What is the exact dataset and target variable in Phase 2?
* **Answer:** *"The dataset is `training_labels_incident_quarantined.csv`, containing 357,124 lane-level observations generated from microscopic SUMO simulations along a real Bengaluru corridor. The target is `queue_length_m_t_plus_60s`, representing the physical downstream contiguous stopped queue length measured in metres on the identical lane exactly 60 seconds into the future."*

### Q2: Why was a 60-second prediction horizon selected instead of 10s or 300s?
* **Answer:** *"A 10-second horizon is too short for traffic signal controllers to react, as yellow clearance intervals and minimum green times require at least 15–30 seconds to transition safely. Conversely, our earlier 300-second (5-minute) experiments exhibited severe error compounding due to stochastic vehicle turns. A 60-second horizon aligns perfectly with standard urban cycle lengths, providing sufficient lead time for predictive green-extension decisions without excessive forecast degradation."*

### Q3: What feature engineering was performed for the queue model?
* **Answer:** *"We engineered 11 current-state features: 5 numerical features (`queue_length_m`, `vehicle_count`, `halting_vehicle_count`, `mean_speed_mps`, `phase_elapsed_s`) preprocessed using median imputation and standard scaling, and 6 categorical features (`intersection_id`, `approach_id`, `lane_id`, `signal_phase_id`, `signal_state`, `vehicle_composition`) encoded using one-hot encoding with an infrequent category threshold (`min_frequency=25`)."*

### Q4: How does the Hurdle model work and how does it compare to persistence?
* **Answer:** *"Because 97.55% of lane observations have zero queue, standard regression algorithms suffer from downward bias. Our Hurdle model decouples the task: Stage 1 uses a balanced Random Forest Classifier to predict the probability of a non-zero queue ($y > 0$). If the probability exceeds an optimal threshold tuned on validation seed 99, Stage 2 uses a Random Forest Regressor fit strictly on positive queues to predict queue magnitude. On all 112,176 test rows, the Hurdle model achieves 0.055m MAE vs. 0.069m for persistence. On true congestion queues ($N=2,753$), it achieves **2.20m MAE vs. 3.33m for persistence**, delivering a **33.9% error reduction**."*

### Q5: What role does Metaflow play in the architecture?
* **Answer:** *"Metaflow orchestrates the pipeline (`flows/bengaluru_queue_model_flow.py`) across 4 steps: `start`, `train_evaluate`, `acceptance`, and `end`. It enforces seed-isolated splits, executes training in an isolated subprocess, computes cryptographic dataset hashes, checks acceptance gates, and serializes the model binary bytes and metadata directly into versioned run artifacts."*

### Q6: How does the Model Registry enforce quality and security?
* **Answer:** *"`scripts/model_registry_report.py` acts as an automated quality gate. It verifies that the Metaflow run was successful, checks that the serialized model hash matches the expected SHA-256, validates that metadata network and target contracts match, and enforces that candidate validation/test MAEs improve by at least 5% over persistence. Only models passing all gates are eligible for export."*

### Q7: What security defenses are implemented in the FastAPI service?
* **Answer:** *"We enforce two layers of security: (1) Input validation via Pydantic v2 forbids unexpected JSON fields (`extra='forbid'`), validates non-negative numbers, rejects non-finite floats (`allow_inf_nan=False`), and sanitizes string IDs. (2) Pre-deserialization integrity checking uses constant-time `hmac.compare_digest()` to verify the raw binary SHA-256 hash before calling `joblib.load()`, eliminating arbitrary code execution vulnerabilities from malicious or corrupted pickles."*

### Q8: How is the Docker container designed and hardened?
* **Answer:** *"The Dockerfile uses `python:3.12-slim` and installs only the 7 pinned dependencies in `requirements-api.txt`. It runs strictly as an unprivileged user (`apiuser`, UID 10001). Its `.dockerignore` uses an allowlist pattern (`**` ignored by default) that completely excludes datasets, SUMO networks, model weights, git objects, and secrets. If the model is missing, it starts safely in degraded mode where `/health` returns HTTP 503."*

### Q9: What does your GitHub Actions CI/CD pipeline verify?
* **Answer:** *"`phase2-ci.yml` triggers on pushes and pull requests to `main` and `phase2-*`. It compiles Python bytecode, runs all 34 unit tests, statically validates Metaflow DAGs, and builds the container image. Production deployment is strictly gated: ordinary pushes skip deployment. Deployment requires a manual `workflow_dispatch` on `main` with `deploy_production: true`, which triggers the Render webhook and polls `/health` until HTTP 200 is verified."*

### Q10: Why is Phase 2 data not in DVC and what is DVC's actual role?
* **Answer:** *"DVC was established in Phase 1 to track historical citywide volume data and raw OSM road networks. In Phase 2, simulation labels and models were tracked directly via Metaflow run artifacts. DVC tracks `bengaluru_osm_sim.net.xml.dvc`, but has zero pointer files for `training_labels_incident_quarantined.csv`. Calling Phase 2 data 'DVC-managed' was an audited documentation bug; Phase 2 simulation data is managed via Metaflow and local simulation storage."*

### Q11: How is data drift monitored using PSI?
* **Answer:** *"`sumo/bengaluru_osm/monitoring.py` calculates the Population Stability Index using reference quantile bins with infinite tail expansion and zero-division clipping ($10^{-6}$). Features with $\text{PSI} < 0.10$ are flagged as `'stable'`, $0.10 \le \text{PSI} < 0.25$ as `'watch'`, and $\ge 0.25$ as `'high'`. Performance metrics are evaluated across an exact 8-key composite join and stratified across demand levels, vehicle compositions, and intersection IDs."*

### Q12: Why didn't predictive control outperform adaptive control in SUMO?
* **Answer:** *"In our Bengaluru corridor simulations, predictive control achieved 507.27s travel time in low demand (vs. 504.08s fixed and 507.61s adaptive) and 536.74s in medium-300 demand (vs. 531.30s fixed and 536.10s adaptive). Two physical factors explain this: (1) 60-second forward predictions on green phases caused unnecessary green extensions due to upstream turning traffic that had not yet reached the stop line, starving cross streets. (2) In high demand, gridlocks triggered SUMO's 300-second vehicle teleport heuristic, corrupting comparisons. Rather than claiming false superiority, we properly flag these runs as `quality_failures`."*

### Q13: What are the primary real-world limitations of this project?
* **Answer:** *"The system is an uncalibrated microscopic simulation prototype. It does not use live Bengaluru traffic camera or GPS probe feeds; vehicle arrival rates and fleet mixes are synthetic assumptions; driver behavior uses standard SUMO IDM defaults without local calibration; and there is no connection to physical municipal traffic signal hardware."*

---

## 6. Unresolved Discrepancies & Mitigation Disclosure

To maintain absolute transparency with evaluators, the following 7 known issues must be stated openly:

1. **Positive-Queue Persistence Baseline Nuance:** On the full 112k test set, persistence achieves 0.069m MAE due to 97.55% zero-inflation. On the positive subset ($N=2,753$), persistence MAE is 3.33m, which the Hurdle model improves to 2.20m (33.9% reduction). Evaluators must be shown both numbers.
2. **Missing Original Training Dataset:** `training_labels_incident_quarantined.csv` (105 MB) was omitted from Git and resides on teammate Pranjali's machine. Rerunning training requires copying this file.
3. **Missing Model Binaries in Local Clone:** Both the API candidate (`72bc01ba...`) and Metaflow model (`167b523f...`) are gitignored and absent locally. Live container inference requires staging the binary into `models/bengaluru/`.
4. **Missing SUMO Network Payload:** `bengaluru_osm_sim.net.xml` (242 MB) is tracked via DVC pointer, but the raw XML is absent locally. Rerunning SUMO simulations requires a DVC pull or local file copy.
5. **Dual Model Hash Lineage:** The API metadata pins prototype hash `72bc01ba...`, whereas Metaflow canonical run `1794405200312669` produced hash `167b523f...`. Promoting the Metaflow model requires updating `QUEUE_MODEL_SHA256` across `render.yaml`, `Dockerfile`, and metadata JSON.
6. **Lack of Live Production Monitoring:** Monitoring is implemented as an offline batch replay engine; Prometheus metrics, Grafana dashboards, and live telemetry streaming are future work.
7. **No Independent Public Hosted Inference Verification:** In CI Run `43060494475`, the runner verified that `/health` returned HTTP 200 on Render, but `/predict` was smoke-tested only locally in Docker, not over the public internet.

---

## 7. Final Demonstration Readiness Classification

| Demonstration Component | Readiness Verdict | Current Execution Capability |
|---|---|---|
| **Git Working Tree & Commits** | **`READY`** | 100% clean on `main` at `d858900`; runnable immediately. |
| **Unit Test Suite (34 Tests)** | **`READY`** | 100% passing in 0.15s; runnable immediately. |
| **Metaflow DAG Static Check** | **`READY`** | Validates DAG syntax and contracts; runnable immediately. |
| **API Schema & 503 Degradation** | **`READY`** | Uvicorn starts in degraded mode; returns HTTP 503 on `/health` and HTTP 422 on bad inputs. |
| **Archived Smoke Test Inference** | **`READY (ARCHIVED)`** | Single held-out row (5.17m vs. 11.0m) ready to inspect in `demo_smoke_20261111/`. |
| **CI/CD Build & Deploy Telemetry** | **`READY (REMOTE)`** | Verified GitHub Actions runs `43039410684` and `43060494475` ready to inspect. |
| **Offline Monitoring Test Suite** | **`READY`** | 3/3 monitoring tests pass in 0.03s; runnable immediately. |
| **Live Model Retraining** | **`BLOCKED`** | Blocked by missing 357k training dataset CSV. |
| **Live Container Inference** | **`BLOCKED`** | Blocked by missing `.joblib` binary in local `models/bengaluru/`. |
| **Live SUMO Microscopic Simulation**| **`BLOCKED`** | Blocked by missing network XML payload and SUMO binaries. |

---

## 8. Summary Conclusion & Master Sign-Off

The Phase 2 Traffic MLOps codebase represents a **fully hardened, mathematically sound, and rigorously documented engineering artifact**. 

All 34 unit tests pass, input validation and deserialization defenses are verified, container configurations follow strict non-root security standards, and CI/CD pipelines enforce gated production releases. Where microscopic simulation challenges occurred, the project maintained scientific integrity by rejecting invalid teleport runs and disclaiming false controller superiority.

**AUDIT AND DEMONSTRATION PLAN COMPLETE. NO FURTHER REPOSITORY MUTATIONS PERFORMED.**

