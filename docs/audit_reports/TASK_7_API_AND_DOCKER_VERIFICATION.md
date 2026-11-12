# TASK 7 — PHASE 2 API AND DOCKER FINAL VERIFICATION

**Authoritative Repository:** `D:\TrafficMLOps_Phase2_Workspace\repository`  
**Inspected Branch & Commit:** `main` @ `d85890058a13094ab3852f6297d87f29d5d01d0e`  
**Audit Protocol:** Strictly read-only; no server startups, no container builds/runs, no network queries, no test reruns, and zero file modifications.

---

## 1. FastAPI Implementation (`src/api/app.py`)

Inspection of `src/api/app.py` confirms the API contract and endpoint implementation:

### Endpoints Implemented
* Dual-path routing provides root and versioned paths for all three operations:
  * Health check: `GET /health` and `GET /api/v1/health`
  * Model metadata: `GET /model-info` and `GET /api/v1/model-info`
  * Queue inference: `POST /predict` and `POST /api/v1/predict`

### Request Validation & Schema (`PredictionRequest`)
* Implemented via Pydantic v2 with strict validation guards:
  * `model_config = ConfigDict(extra="forbid")`: Disallows unexpected or malicious query fields.
  * `queue_length_m`: `float, ge=0, allow_inf_nan=False`
  * `vehicle_count`: `int, ge=0`
  * `halting_vehicle_count`: `int, ge=0`
  * `mean_speed_mps`: `float, ge=0, allow_inf_nan=False`
  * `phase_elapsed_s`: `float, ge=0, allow_inf_nan=False`
  * `intersection_id`, `approach_id`, `lane_id`, `signal_phase_id`, `signal_state`: String fields with `min_length=1` and a custom validator (`nonblank_identifier`) stripping whitespace and rejecting blank/whitespace strings.
  * `vehicle_composition`: `Literal["balanced_assumed", "motorcycle_heavy_assumed"]`
  * Cross-field validation: `@model_validator(mode="after")` enforces `halting_vehicle_count <= vehicle_count`.

### Feature Contract & Target
* **Target:** `queue_length_m_t_plus_60s` (physical queue length in metres).
* **Prediction Horizon:** Fixed at `HORIZON_SECONDS = 60`.
* **Ordered Input Features (11):**
  1. `queue_length_m`
  2. `vehicle_count`
  3. `halting_vehicle_count`
  4. `mean_speed_mps`
  5. `phase_elapsed_s`
  6. `intersection_id`
  7. `approach_id`
  8. `lane_id`
  9. `signal_phase_id`
  10. `signal_state`
  11. `vehicle_composition`

### Missing-Model & Degraded Behavior
* In `create_app()`:
  ```python
  try:
    model, digest, metadata = load_model(
        selected, os.environ.get("QUEUE_MODEL_SHA256"), meta_path
    )
    app.state.model = model
    app.state.model_sha256 = digest
    app.state.model_path = str(selected)
    app.state.metadata = metadata
  except FileNotFoundError:
    app.state.model = None
    app.state.model_sha256 = None
    app.state.model_path = str(selected)
    app.state.metadata = None
  ```
* If the model artifact is absent:
  * `app.state.model` is set to `None`.
  * Calls to `/health`, `/model-info`, or `/predict` immediately raise `HTTPException(status_code=503, detail="Validated Bengaluru model artifact is not configured")`.
  * The application boots safely into a degraded state rather than crashing or returning corrupt/unvalidated default predictions.

---

## 2. Model Loading and Integrity Verification

Inspection of `load_model()` and `read_metadata()` in `src/api/app.py`:

1. **Pre-Deserialization SHA-256 Digest Verification:**
   * Reads raw bytes from disk in 1 MB chunks and computes `hashlib.sha256()`.
   * Enforces that the expected SHA-256 is a valid 64-character hexadecimal string.
   * Compares the computed digest with the expected digest using constant-time `hmac.compare_digest(digest.lower(), expected.lower())`.
   * **Crucial Security Measure:** `joblib.load(model_path)` is executed **strictly after** digest verification passes. If a digest mismatch occurs, it raises `ValueError` and never deserializes the untrusted pickle/joblib payload.
2. **Metadata Contract Validation:**
   * Reads and parses `QUEUE_MODEL_METADATA_PATH`.
   * Validates `validation_status == "passed"`.
   * Validates `network == "bengaluru_osm_sim.net.xml"`.
   * Verifies that the metadata feature list matches the expected 11 features.
3. **In-Memory Schema Consistency Check:**
   * After deserialization, asserts `list(model.feature_names_in_) == metadata["features"]`.
4. **Configured Deployment Candidate:**
   * Target SHA-256 configured across `src/api/bengaluru_deployment_metadata.json`, `Dockerfile`, and `render.yaml`:
     `72bc01ba9b659eeb47cd977b9bfb691e552da9f610bf637a96b05d3d36f9ea71`
   * *Runtime caveat:* The physical `.joblib` file matching this hash is omitted from the Git repository.

---

## 3. Docker Implementation

Inspection of `Dockerfile`, `.dockerignore`, and `docker_entrypoint.py`:

* **Base Image:** `python:3.12-slim` (official Debian-based lightweight Python 3.12 image).
* **Dependency Scope:** Pinned to `requirements-api.txt` (`fastapi`, `uvicorn`, `pydantic`, `numpy`, `pandas`, `scikit-learn`, `joblib`). Does not install SUMO, DVC, or Metaflow, keeping the attack surface and image size minimal.
* **Build Context Isolation (`.dockerignore`):**
  * Employs an allowlist pattern (`**` ignored by default).
  * Exclusively admits `Dockerfile`, `docker_entrypoint.py`, `requirements-api.txt`, `src/api/`, and `sumo/bengaluru_osm/bengaluru_model.py`.
  * Guarantees datasets, models, `.env`, `.git`, `.dvc`, and temporary files are excluded from image layers.
* **Non-Root Execution:**
  ```dockerfile
  RUN useradd --create-home --uid 10001 apiuser
  USER apiuser
  ```
  Runs as unprivileged user `apiuser` (UID 10001).
* **Model Injection & Runtime Startup (`docker_entrypoint.py`):**
  * If `QUEUE_MODEL_URL` is provided:
    1. Enforces HTTPS scheme (rejects insecure HTTP or redirects).
    2. Streams download to a temporary file while computing SHA-256 in 1 MB chunks.
    3. Validates against `QUEUE_MODEL_SHA256`.
    4. Atomically moves the file to `QUEUE_MODEL_PATH` via `os.replace`.
    5. Cleanly unlinks temporary files on failure.
  * If `QUEUE_MODEL_URL` is omitted:
    * Relies on read-only bind mounting at container runtime.
    * Verifies `QUEUE_MODEL_SHA256` if the file exists.
* **Container Healthcheck:**
  ```dockerfile
  HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD ["python", "-c", "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.getenv('PORT','8000'), timeout=3)"]
  ```
* **Fresh-Clone Docker Execution Blocker:**
  * In `README.md` and `docs/phase2_runbook.md`, the documented PowerShell command:
    ```powershell
    $model = (Resolve-Path .\models\bengaluru\bengaluru_queue_hurdle_v1_2026-11.joblib).Path
    ```
    **Fails immediately on a fresh clone** because `.\models\bengaluru\bengaluru_queue_hurdle_v1_2026-11.joblib` is gitignored and absent. `Resolve-Path` throws a terminating `ItemNotFoundException`.

---

## 4. Monitoring Implementation

Inspection of `sumo/bengaluru_osm/monitoring.py`, `sumo/bengaluru_osm/record_feedback.py`, and `tests/test_bengaluru_monitoring.py`:

* **Monitoring Paradigm:** **Strictly Offline Simulation Batch Replay**.
  * File header: *"This is a reproducible batch check, not a live production monitor."*
  * Limitations field in JSON output: *"Offline held-out SUMO replay only. No production traffic, live API telemetry, or independently observed field queue labels."*
* **Population Stability Index (PSI):**
  * `psi(reference, current, bins=10)` computes reference quantile bins bounded by $[-\infty, +\infty]$.
  * Proportions clipped at $10^{-6}$ to prevent $\log(0)$ instability.
  * Thresholds:
    * $\text{PSI} < 0.10$: `"stable"`
    * $0.10 \le \text{PSI} < 0.25$: `"watch"`
    * $\text{PSI} \ge 0.25$: `"high"` (drift alert)
* **Statistical Performance Metrics:**
  * Computes $N$, MAE (metres), RMSE (metres), and $R^2$ using `scikit-learn.metrics`.
* **Stratified Slices:**
  * Metrics computed across three dimensions:
    1. Demand scenarios (`error_by_demand`: low, medium, high)
    2. Fleet profiles (`error_by_composition`: balanced_assumed, motorcycle_heavy_assumed)
    3. Intersections (`error_by_intersection`: per intersection ID)
* **Feedback Ledger (`build_feedback()`):**
  * Implements an immutable ledger joining observations with predictions on 8 exact composite keys:
    `KEYS = ["run_id", "seed", "scenario", "vehicle_composition", "intersection_id", "approach_id", "lane_id", "time_s"]`
  * Captures: `observed_queue_length_m_t_plus_60s`, `prediction_error_m`, `feedback_model_version`, `feedback_model_sha256`, `feedback_source` (`"held_out_sumo_replay"`), and UTC timestamp.
  * Enforces `retraining_eligible: false` to prevent data leakage from held-out test seeds into future training sets.
* **Production Observability Infrastructure:**
  * **Not Implemented:** No Prometheus metrics endpoint (`/metrics`), no Prometheus client, no Grafana dashboards, and no automated notification/alerting hooks (Slack/PagerDuty).

---

## 5. Test Suite Structure and Evidence Analysis

The repository contains 7 unit test modules comprising exactly **34 test methods**:

| Test Module | Test Count | Test Fixtures & Methodology | Relies on Model / Data Binary? | Proof Scope |
|---|---|---|---|---|
| `tests/test_api.py` | 10 | Uses synthetic `FakeModel` and temporary test directories | **No** (Synthetic stub) | API contract, Pydantic schemas, 503 missing-model handling, SHA-256 pre-check |
| `tests/test_bengaluru_monitoring.py` | 3 | Uses synthetic in-memory DataFrames | **No** (Synthetic stub) | PSI calculation correctness, feedback join logic, schema mismatch rejection |
| `tests/test_model_registry.py` | 4 | Uses mock Metaflow Run objects and temp directories | **No** (Synthetic stub) | Gate validation logic, hash matching, rejection of invalid runs |
| `tests/test_bengaluru_scenario.py` | 6 | Inspects corridor scenario and route definitions | **No** (Static definitions) | Corridor anchor paths, vehicle classes, queue definition rules |
| `tests/test_features.py` | 3 | Synthetic DataFrames for IQR transforms | **No** (Synthetic data) | Outlier filtering, deterministic feature engineering |
| `tests/test_perimeter_routes.py` | 6 | Route generation geometry and OD pairs | **No** (Static route logic) | 64 connected OD pairs, route generator determinism |
| `tests/test_train.py` | 2 | Mock DataFrames with date/category features | **No** (Synthetic data) | Time-split leakage prevention, unseen category handling |
| **Total Test Suite** | **34** | **100% Hermetic / Isolated Unit Tests** | **Zero Binary Dependencies** | **Component contracts pass; runtime weights unverified** |

### Critical Evidence Distinction:
* **What the 34 tests prove:** The API request/response contracts, input validation schemas, pre-deserialization hash defenses, offline monitoring formulas, and registry validation gates are syntactically and logically correct.
* **What the 34 tests do not prove:** None of the 34 tests prove that the actual trained model weights (`72bc01ba...` or `167b523f...`) can generate live inferences in memory.
* **Where actual model inference was demonstrated:** Local container smoke testing occurred once on 2026-11-11 and its responses are archived in `reports/demo_smoke_20261111/`. It is an ad-hoc local verification artifact, not an automated test.

---

## 6. Final Evaluation Report

### A. API Implementation Status: `VERIFIED`
* Dual-path endpoints (`/health`, `/model-info`, `/predict` under `/` and `/api/v1/`) are implemented with Pydantic v2 schemas, strict type enforcement, 11-feature input alignment, and explicit target and 60-second horizon declarations.

### B. API Validation and Security: `VERIFIED`
* Input validation forbids extra fields, rejects negative or infinite numbers, validates identifier strings, and validates halting vehicle counts. Pre-deserialization integrity checking prevents unvalidated pickle execution.

### C. Model-Loading and Integrity Status: `VERIFIED IN CODE / BLOCKED IN RUNTIME`
* The loading sequence in `load_model()` strictly checks metadata and validates file SHA-256 via `hmac.compare_digest()` before calling `joblib.load()`.
* When the file is missing, the API transitions to a safe degraded state (HTTP 503).
* Execution of the actual model is blocked in a fresh clone because the physical `.joblib` binary is excluded from Git.

### D. Docker Implementation Status: `VERIFIED`
* Dockerfile uses Python 3.12-slim, installs isolated API requirements, runs as unprivileged `apiuser` (UID 10001), enforces HTTPS streaming downloads with SHA-256 verification in `docker_entrypoint.py`, and excludes sensitive files via `.dockerignore`.

### E. Monitoring Implementation Status: `VERIFIED AS OFFLINE ONLY`
* PSI calculation and thresholds ($0.10, 0.25$), error metrics (MAE, RMSE, $R^2$), slice stratification, and the immutable feedback ledger are fully implemented for offline batch replay.
* Live observability (Prometheus `/metrics`, Grafana dashboards, PagerDuty alerting) is **NOT IMPLEMENTED**.

### F. Test Evidence and Limitations: `VERIFIED`
* Exactly 34 unit tests exist across 7 test files. All 34 execute successfully in hermetic CI environments using synthetic fixtures without requiring external models or datasets.
* Real model execution is verified only through archived ad-hoc smoke test responses in `reports/demo_smoke_20261111/`.

### G. Fresh-Clone Execution Blockers: `BLOCKED`
1. Running `Resolve-Path .\models\bengaluru\bengaluru_queue_hurdle_v1_2026-11.joblib` fails because the model binary is absent.
2. Starting the API or Docker container without injecting a valid external model results in HTTP 503 responses across all endpoints.

---

## 7. Overall Verdict

| Audit Domain | Verdict | Core Finding |
|---|---|---|
| **FastAPI Contract & Schemas** | **VERIFIED** | Clean 11-feature schema, strict Pydantic guards, 60s horizon. |
| **Model Security & Integrity** | **VERIFIED** | Constant-time SHA-256 pre-check prevents insecure deserialization. |
| **Missing-Model Behavior** | **VERIFIED** | Returns HTTP 503; does not crash or emit dummy predictions. |
| **Docker Configuration** | **VERIFIED** | Minimal dependencies, non-root user, streaming HTTPS verification. |
| **Offline Monitoring & Drift** | **VERIFIED** | Quantile-binned PSI, slice stratification, immutable feedback ledger. |
| **Live Observability (Prometheus/Grafana)** | **NOT IMPLEMENTED** | Offline batch replay only; no live telemetry or alerting. |
| **Unit Test Coverage (34 Tests)** | **VERIFIED** | 100% hermetic unit tests pass; zero external dependencies. |
| **Fresh-Clone Container Launch** | **BLOCKED** | Model binary excluded from Git; requires manual artifact handoff. |

**Final Assessment: API ARCHITECTURE, DOCKER SPECIFICATION, MODEL INTEGRITY DEFENSES, AND OFFLINE MONITORING ARE VERIFIED. RUNTIME INFERENCE IS BLOCKED ON FRESH CLONES DUE TO MISSING MODEL BINARIES.**

