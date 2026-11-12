# TASK 6 — PHASE 2 CI/CD AND RENDER DEPLOYMENT EVIDENCE AUDIT

**Authoritative Repository:** `D:\TrafficMLOps_Phase2_Workspace\repository`  
**Inspected Branch & Commit:** `main` @ `d85890058a13094ab3852f6297d87f29d5d01d0e`  
**Audit Protocol:** Strictly read-only; no file mutations in repository, no workflow triggers, no network mutations, zero credential exposure.

---

## 1. CI Workflow Inspection (`.github/workflows/phase2-ci.yml`)

Inspection of `.github/workflows/phase2-ci.yml` confirms the following architecture:

* **Workflow Triggers:**
  * `push`: branches `[main, "phase2-*"]`
  * `pull_request`: all PR branches
  * `workflow_dispatch`: manual execution with boolean input `deploy_production` (default `false`, description: *"Trigger Render deployment to the protected production environment"*)
* **Permissions:** Read-only repository access (`permissions: contents: read`).
* **Python Runtime:** Explicitly pinned to Python `3.12` via `actions/setup-python@v5`.
* **Dependency Installation:**
  ```bash
  python -m pip install -r requirements-phase2.txt -r requirements-test-phase1.txt
  ```
  Isolates modern Phase 2 and regression dependencies cleanly without installing legacy unpinned `requirements.txt`.
* **Python Bytecode Compilation:**
  ```bash
  python -m compileall -q src sumo flows scripts tests
  ```
* **Test Suite Scope:**
  ```bash
  python -m unittest discover -s tests -v
  ```
  Discovers and executes the entire 34-test suite (`test_api.py`, `test_bengaluru_monitoring.py`, `test_model_registry.py`, and `test_pipeline_reproducibility.py`).
* **Metaflow Static Graph Validation:**
  ```bash
  python flows/queue_model_flow.py --metadata=local --datastore=local check
  python flows/bengaluru_queue_model_flow.py --metadata=local --datastore=local check
  ```
  Validates both DAG structures statically without executing heavy simulation or training steps.
* **Docker Container Build:**
  ```bash
  docker build --tag traffic-queue-api:ci .
  ```
  Builds the container image within the Ubuntu runner to verify build reproducibility.
* **Deployment Gate Structure:**
  * Positioned in a separate `deploy` job with `needs: checks-and-image`.
  * Guard condition:
    ```yaml
    if: github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' && inputs.deploy_production
    ```
  * Requires explicit manual boolean dispatch (`inputs.deploy_production == true`) and execution on `refs/heads/main`.
  * Bound to GitHub Actions `environment: production`.
  * **Automatic push deployments are strictly disabled.** Ordinary pushes to `main` or feature branches skip the deployment job entirely.

---

## 2. GitHub Actions Run Evidence Verification

The three specified runs were inspected via read-only queries to the GitHub Actions REST API:

| Metric / Attribute | Run 1: `43036696130` | Run 2: `43039410684` | Run 3: `43060494475` |
|---|---|---|---|
| **Workflow Name** | `Phase 2 CI` | `Phase 2 CI` | `Phase 2 CI` |
| **Event Type** | `push` | `push` | `workflow_dispatch` (`deploy_production: true`) |
| **Branch** | `phase2-completion-20261111` | `main` | `main` |
| **Head SHA** | `a85972c61e4698402741f1ae01fa3c62547b1c7b` | `d85890058a13094ab3852f6297d87f29d5d01d0e` | `d85890058a13094ab3852f6297d87f29d5d01d0e` |
| **Created Timestamp** | `2026-11-11T14:15:17Z` | `2026-11-11T14:32:14Z` | `2026-11-11T16:39:34Z` |
| **Overall Conclusion** | **`success`** | **`success`** | **`success`** |
| **Job: `checks-and-image`** | `success` (1m 18s) | `success` (1m 19s) | `success` (1m 17s) |
| **Job: `deploy`** | **`skipped`** | **`skipped`** | **`success`** (37s) |
| **Deployment Execution**| Skipped (event `push` on feature branch) | Skipped (event `push` on `main`) | **Executed** (manual dispatch on `main`) |
| **Job Steps Status** | All 12 CI steps passed | All 12 CI steps passed | CI passed + Render trigger passed |
| **Run URL** | https://github.com/PriyankaSrvce/traffic-mlops/actions/runs/43036696130 | https://github.com/PriyankaSrvce/traffic-mlops/actions/runs/43039410684 | https://github.com/PriyankaSrvce/traffic-mlops/actions/runs/43060494475 |

---

## 3. Render Deployment Configuration Inspection

Inspected files: `render.yaml`, `Dockerfile`, `docker_entrypoint.py`, and `src/api/app.py`.

* **Service Definition:**
  * Service name: `traffic-queue-api`
  * Runtime: `docker` (`dockerfilePath: ./Dockerfile`, `dockerContext: .`)
  * Plan: `free`
  * Port: `10000` (Render default mapped to container)
  * Health check path: `/health`
* **Auto-Deployment Setting:**
  * `autoDeployTrigger: off`
  * Render's native auto-deployment on Git push is disabled. Deployments occur only when GitHub Actions issues an authenticated POST request to `RENDER_DEPLOY_HOOK_URL`.
* **Model Configuration Mechanism:**
  * Environment variables in `render.yaml`:
    * `QUEUE_MODEL_PATH: /tmp/queue-model.joblib`
    * `QUEUE_MODEL_METADATA_PATH: /app/src/api/bengaluru_deployment_metadata.json`
    * `QUEUE_MODEL_URL: sync: false` (must be configured manually in Render dashboard pointing to an HTTPS artifact host)
    * `QUEUE_MODEL_SHA256: 72bc01ba9b659eeb47cd977b9bfb691e552da9f610bf637a96b05d3d36f9ea71`
* **Model Integrity & Pre-Deserialization Security:**
  * In `docker_entrypoint.py`:
    1. Validates that `QUEUE_MODEL_URL` uses HTTPS.
    2. Streams download to a temporary file while computing SHA-256.
    3. Enforces that redirect did not divert to a non-HTTPS scheme.
    4. Compares digest with `QUEUE_MODEL_SHA256`; aborts with `ValueError` on mismatch.
    5. Performs an atomic `os.replace` to `QUEUE_MODEL_PATH`.
  * In `src/api/app.py` (`load_model()`):
    1. Reads metadata from `QUEUE_MODEL_METADATA_PATH`.
    2. Validates metadata network (`bengaluru_osm_sim.net.xml`), validation status (`passed`), and feature schema.
    3. Re-computes the model file digest.
    4. Executes timing-safe `hmac.compare_digest()` against expected SHA-256 **prior to calling `joblib.load()`**.
* **Fail-Safe Mechanism:**
  * If the model cannot be found or fails verification:
    * `docker_entrypoint.py` crashes before starting Uvicorn (if `QUEUE_MODEL_URL` fails).
    * If local file is missing, `app.py` catches `FileNotFoundError`, sets `app.state.model = None`, and endpoints `/health`, `/model-info`, and `/predict` return **`HTTP 503 Service Unavailable`** (`{"detail": "Validated Bengaluru model artifact is not configured"}`).
    * This prevents unvalidated or corrupted models from serving predictions, and causes Render health checks to fail cleanly.

---

## 4. Documented Live Deployment Evidence Audit

Auditing claims regarding live deployment:

### Claim A: Render service domain is `traffic-queue-api.onrender.com`
* **Finding:** **NOT VERIFIED IN REPOSITORY EVIDENCE**.
* **Analysis:** The string `onrender.com` does not appear in any repository file or commit. The service name in `render.yaml` is `traffic-queue-api`, which is the slug Render uses to construct default URLs, and GitHub Secret `RENDER_SERVICE_URL` was passed in CI. However, the exact public domain is not recorded in the repository files.

### Claim B: Public `/health` returned HTTP 200
* **Finding:** **VERIFIED IN CI STEP; NOT VERIFIED ON PUBLIC INTERNET BY AUDIT**.
* **Analysis:** In GitHub Actions Run `43060494475`, the deployment step executed:
  ```bash
  curl --fail --silent --show-error --request POST "$RENDER_DEPLOY_HOOK_URL"
  for attempt in $(seq 1 30); do
    status=$(curl --silent --output /dev/null --write-out "%{http_code}" --max-time 10 "$RENDER_SERVICE_URL/health" || true)
    if [ "$status" = "200" ]; then
      echo "Render service health check passed."
      exit 0
    fi
    sleep 20
  done
  ```
  The step exited 0 and logged `Render service health check passed.` within 37 seconds. Since `/health` returns HTTP 503 when the model is not loaded, receiving HTTP 200 confirms that the service responding at `$RENDER_SERVICE_URL` had a valid model loaded. However, per strict audit rules, no external network requests were made to test current live availability.

### Claim C: Public `/model-info` returned HTTP 200
* **Finding:** **VERIFIED AS LOCAL DOCKER SMOKE TEST ONLY; NOT VERIFIED ON RENDER**.
* **Analysis:** Captured response exists in `reports/demo_smoke_20261111/model_info.json`. The CI deployment workflow did not poll `/model-info`.

### Claim D: Public `/predict` returned HTTP 200 with prediction 5.1657m against 11m label
* **Finding:** **VERIFIED AS LOCAL DOCKER SMOKE TEST ONLY; NOT A LIVE HOSTED PREDICTION**.
* **Analysis:** This exact response is preserved in `reports/demo_smoke_20261111/heldout_positive_sample_result.json`:
  ```json
  {
    "prediction": {
      "predicted_queue_length_m": 5.1656687762301035,
      "target": "queue_length_m_t_plus_60s",
      "horizon_seconds": 60,
      "model_version": "bengaluru_queue_hurdle_v1_2026-11",
      "model_sha256": "72bc01ba9b659eeb47cd977b9bfb691e552da9f610bf637a96b05d3d36f9ea71"
    }
  }
  ```
  `README.md` and `reports/demo_smoke_20261111/README.md` explicitly declare:
  > *"This is local smoke-test evidence only. It does not show a public deployment or real-time Bengaluru traffic data."*

### Distinct Separation of Verification Dimensions:

```
[GitHub Actions Workflow Deploy Job] ------------> VERIFIED (Run 43060494475 exited 0 in 37s)
[Render Deploy Hook Acceptance] ------------------> VERIFIED (POST returned success)
[Service Health Check in CI Runner] --------------> VERIFIED (Runner curl received HTTP 200)
[Public Web Service Accessibility] ---------------> NOT VERIFIED (No external network probes)
[Public Model Inference (/predict)] --------------> NOT VERIFIED (Only /health was polled in CI)
[Documented 5.1657m vs 11m Prediction] -----------> VERIFIED AS LOCAL DOCKER ONLY
[Hosted Prediction Quality Evaluation] -----------> NOT VERIFIED (Single-row local smoke test)
```

---

## 5. Final Report & Evaluation Matrix

### A. CI Implementation Status: `VERIFIED`
* Workflow file `.github/workflows/phase2-ci.yml` is syntactically valid, statically checks Metaflow DAGs, runs all 34 tests, compiles Python bytecode, builds Docker images, and enforces strict gating.

### B. GitHub Actions Run Evidence: `VERIFIED`
* Verified via live GitHub Actions REST API:
  * Run `43036696130`: Passed on feature branch commit `a85972c`; deploy job skipped.
  * Run `43039410684`: Passed on `main` merge commit `d858900`; deploy job skipped.
  * Run `43060494475`: Passed on `main` commit `d858900` via manual `workflow_dispatch`; deploy job passed.

### C. Deployment Gate Verification: `VERIFIED`
* The deployment job cannot be triggered by ordinary pushes. It requires explicit `workflow_dispatch` on `refs/heads/main` with `deploy_production: true`, and depends on prior completion of all unit tests and container builds.

### D. Render Configuration Verification: `VERIFIED`
* `render.yaml`, `Dockerfile`, and `docker_entrypoint.py` provide a secure deployment specification with auto-deploys disabled, health check path configured, HTTPS enforcement, streaming SHA-256 verification, and timing-safe pre-deserialization validation.

### E. Live Deployment Evidence Status: `PARTIALLY VERIFIED`
* **Verified:** The GitHub Actions runner successfully triggered the deploy webhook and received HTTP 200 on `/health` during Run `43060494475`.
* **Not Verified:** Live external access from public internet; no record in repository of `/predict` or `/model-info` having been queried against the hosted Render URL.

### F. Model Availability Impact: `BLOCKED LOCALLY / CONFIGURED REMOTELY`
* Locally, model binaries (`72bc01ba...` and `167b523f...`) are absent from the Git clone.
* Remotely, the Render deployment succeeded during CI, indicating that `QUEUE_MODEL_URL` in the Render environment was populated with a reachable, valid HTTPS artifact matching hash `72bc01ba...`.

### G. Remaining Blockers:
1. **Physical Binary Handoff:** Local execution of the API and container remains blocked until teammate Pranjali provides the model `.joblib` binary.
2. **Missing Evidence Report:** `reports/phase2_render_deployment_20261111.md` referenced in documentation checklists does not exist on disk.
3. **Model Hash Alignment:** Once the verified Metaflow artifact (`167b523f...`) is staged, `render.yaml` and `bengaluru_deployment_metadata.json` must be updated to align API metadata with Metaflow run `1794405200312669`.

---

## 6. Overall Verdict

| Audit Domain | Verdict | Summary Evidence |
|---|---|---|
| **CI Implementation** | **VERIFIED** | Python 3.12, 34 tests discovered, Metaflow check, Docker build, strict gating. |
| **CI Execution (commit `d858900`)** | **VERIFIED** | Runs `43039410684` and `43060494475` succeeded on exact main commit. |
| **Deployment Gate** | **VERIFIED** | Manual dispatch + main ref + explicit boolean input required; pushes skip deploy. |
| **Render Blueprint & Security** | **VERIFIED** | `autoDeploy: off`, HTTPS check, streaming SHA-256 check, non-root user `apiuser`. |
| **Documented 5.1657m Inference** | **VERIFIED (LOCAL)** | Stored in `reports/demo_smoke_20261111/`; proven to be local Docker, not hosted. |
| **Hosted Inference & Evaluation** | **NOT VERIFIED** | Only `/health` was polled in CI; no hosted `/predict` evidence exists. |
| **Local Model Runtime** | **BLOCKED** | `.joblib` binary excluded from Git; local testing blocked pending handoff. |

**Final Assessment: CI/CD ARCHITECTURE VERIFIED; RENDER DEPLOYMENT GATING VERIFIED; HOSTED HEALTH CONFIRMED IN CI TELEMETRY; HOSTED PREDICTION REMAINS UNVERIFIED.**

