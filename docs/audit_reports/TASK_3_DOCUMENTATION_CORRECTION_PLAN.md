# TASK 3 — Phase 2 Documentation Correction Plan

**Authoritative Repository:** `D:\TrafficMLOps_Phase2_Workspace\repository`  
**Reference Findings:** [`reports/TASK_2_DOCUMENTATION_AUDIT.md`](file:///d:/TrafficMLOps_Phase2_Workspace/reports/TASK_2_DOCUMENTATION_AUDIT.md) and [`reports/TASK_9_DOCUMENTATION_CONSISTENCY_AUDIT.md`](file:///d:/TrafficMLOps_Phase2_Workspace/reports/TASK_9_DOCUMENTATION_CONSISTENCY_AUDIT.md)  
**Status:** Strictly read-only remediation plan; no repository mutations applied.

---

## Objective

Provide the exact, line-by-line verbatim textual replacements for all primary documentation inconsistencies identified during the Phase 2 audits. These corrections reconcile the documentation with ground-truth repository code, test results, and CI/CD execution records prior to viva defense.

---

## 1. Issue 1: Unit Test Count Discrepancy (32 vs. 34 Tests)

### Affected File & Section
* **File:** [`docs/phase2_completion_report.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/docs/phase2_completion_report.md#L11)
* **Section:** *Summary of completed items*, Bullet 2

### Existing Statement
> `- The full unittest suite passed locally: 32 tests, both in the extracted project and in a clean-checkout simulation worktree.`

### Proposed Replacement Wording
> `- The full unit test suite passes locally: **34 tests across 7 test modules**, with 0 failures and 0 errors in Python 3.12 (WSL/Linux and Windows). The earlier pre-merge test count was 32 prior to the addition of the Metaflow model registry verification tests in commit 81256d3.`

### Evidence Verification & Confidence
* **Evidence:** Running `python -m unittest discover -s tests -v` executes 34 tests across:
  * `tests/test_api.py` (10 tests)
  * `tests/test_bengaluru_monitoring.py` (3 tests)
  * `tests/test_bengaluru_scenario.py` (6 tests)
  * `tests/test_features.py` (3 tests)
  * `tests/test_model_registry.py` (4 tests)
  * `tests/test_perimeter_routes.py` (6 tests)
  * `tests/test_train.py` (2 tests)
  Total = 34 tests.
* **Confidence:** 100% Verified.

---

## 2. Issue 2: False Claim of DVC Tracking for Phase 2 Dataset

### Affected File & Section
* **File:** [`docs/phase2_artifact_viva_guide.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/docs/phase2_artifact_viva_guide.md#L19)
* **Section:** *Artifact mapping / Key files and evidence roles*, Table row 3

### Existing Statement
> `| sumo/bengaluru_osm/datasets/osm_v2b/training_labels_incident_quarantined.csv (DVC-managed payload, not in Git) | The 357,124-row simulation dataset... |`

### Proposed Replacement Wording
> `| sumo/bengaluru_osm/datasets/osm_v2b/training_labels_incident_quarantined.csv (Simulation dataset, not in Git) | The 357,124-row simulation dataset. It is stored on local simulation storage and excluded from Git; it is not tracked in the Phase 1 DVC pipeline (dvc.yaml). |`

### Evidence Verification & Confidence
* **Evidence:** As proven in Tasks 5 and 10, `training_labels_incident_quarantined.csv` has no `.dvc` pointer file in Git history and is not defined in `dvc.yaml` or `dvc.lock`. DVC tracks exclusively Phase 1 historical data and raw OSM road network XML files.
* **Confidence:** 100% Verified.

---

## 3. Issue 3: Unexecutable Docker Snippet on Fresh Clones

### Affected Files & Sections
* **File 1:** [`README.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/README.md#L58-L66) (Section: *API and Docker*)
* **File 2:** [`docs/phase2_runbook.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/docs/phase2_runbook.md#L60-L68) (Section: *Run the container with local model mount*)

### Existing Statement
```powershell
$model = (Resolve-Path .\models\bengaluru\bengaluru_queue_hurdle_v1_2026-11.joblib).Path
docker run --rm -p 8000:8000 `
  --mount "type=bind,source=$model,target=/models/bengaluru_queue_hurdle_v1_2026-11.joblib,readonly" `
  -e QUEUE_MODEL_PATH=/models/bengaluru_queue_hurdle_v1_2026-11.joblib `
  -e QUEUE_MODEL_METADATA_PATH=/app/src/api/bengaluru_deployment_metadata.json `
  -e QUEUE_MODEL_SHA256=72bc01ba9b659eeb47cd977b9bfb691e552da9f610bf637a96b05d3d36f9ea71 `
  traffic-queue-api:local
```

### Proposed Replacement Wording
```powershell
# Prerequisites: The model binary is gitignored and must be staged locally before running:
$modelPath = ".\models\bengaluru\bengaluru_queue_hurdle_v1_2026-11.joblib"
if (-not (Test-Path $modelPath)) {
    Write-Warning "Model binary not found at $modelPath. The container can run in degraded mode (health check will return HTTP 503 until a valid model is mounted)."
} else {
    $model = (Resolve-Path $modelPath).Path
    docker run --rm -p 8000:8000 `
      --mount "type=bind,source=$model,target=/models/bengaluru_queue_hurdle_v1_2026-11.joblib,readonly" `
      -e QUEUE_MODEL_PATH=/models/bengaluru_queue_hurdle_v1_2026-11.joblib `
      -e QUEUE_MODEL_METADATA_PATH=/app/src/api/bengaluru_deployment_metadata.json `
      -e QUEUE_MODEL_SHA256=72bc01ba9b659eeb47cd977b9bfb691e552da9f610bf637a96b05d3d36f9ea71 `
      traffic-queue-api:local
}
```

### Evidence Verification & Confidence
* **Evidence:** In a clean checkout, `models/bengaluru/bengaluru_queue_hurdle_v1_2026-11.joblib` does not exist on disk because `*.joblib` is gitignored. Direct execution of `Resolve-Path` throws an unhandled terminating exception. Adding the conditional guard prevents script failure.
* **Confidence:** 100% Verified.

---

## 4. Issue 4: Outdated CI/CD Run and Deployment Documentation

### Affected Files & Sections
* **File 1:** [`README.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/README.md#L74-L76) (Section: *Metaflow, DVC and CI/CD*)
* **File 2:** [`docs/phase2_artifact_viva_guide.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/docs/phase2_artifact_viva_guide.md#L33-L34, #L56)
* **File 3:** [`reports/phase2_verification_20261111.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/reports/phase2_verification_20261111.md#L38-L39)

### Existing Statement
> `GitHub Actions run 43036696130 passed on commit a85972c on branch phase2-completion-20261111; the deployment job was skipped... A Render service, stable HTTPS model URL, Render deploy hook, and service URL have not been configured; no public deployment is claimed.`

### Proposed Replacement Wording
> `Continuous integration is verified via GitHub Actions on the merged main branch (commit d858900):`  
> `1. Push Run 43039410684 passed all compile checks, 34 unit tests, Metaflow DAG validations, and Docker container builds (deploy job was skipped as designed for ordinary pushes).`  
> `2. Manual workflow_dispatch Run 43060494475 (with deploy_production=true) passed all CI checks and successfully executed the gated deployment step (37s), receiving HTTP 200 from the configured Render service health endpoint.`  
> `Public inference endpoints (/predict) were smoke-tested locally in Docker (reports/demo_smoke_20261111/), but have not been probed over the public internet.`

### Evidence Verification & Confidence
* **Evidence:** Live GitHub Actions REST API telemetry confirms Run `43039410684` (push on `main`) and Run `43060494475` (manual dispatch on `main` triggering Render deploy hook) both completed with status `success` on commit `d858900`.
* **Confidence:** 100% Verified.

---

## 5. Issue 5: Deprecation Banner for Legacy Synthetic Grid Results

### Affected File & Section
* **File:** [`reports/final_results_report.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/reports/final_results_report.md#L1-L10)
* **Section:** Header / Top of document

### Existing Statement
No deprecation notice or warning exists. The document immediately presents results from the legacy synthetic $4 \times 4$ grid (claiming a 6.86% reduction in trip duration).

### Proposed Replacement Wording (Insert Banner at Top of File)
> `> [!WARNING]`  
> `> **HISTORICAL PROTOTYPE RECORD — SUPERSEDED BY CURRENT BENGALURU OSM STUDY**`  
> `> This document reports earlier experimental results evaluated on an idealized 4x4 synthetic grid (perimeter_p25_v1).`  
> `> In the current Phase 2 study using the realistic Bengaluru OpenStreetMap corridor (bengaluru_osm_sim.net.xml), predictive control **does not outperform** fixed-time or adaptive control on average travel time (504.08s fixed vs 507.27s predictive in low demand; 531.30s fixed vs 536.74s predictive in medium-300). High-demand runs suffered vehicle teleports and are classified as quality failures.`  
> `> Refer to [reports/phase2_osm_results.md](phase2_osm_results.md) for authoritative Bengaluru corridor findings.`

### Evidence Verification & Confidence
* **Evidence:** Proven in Tasks 8 and 9 through comparative analysis of `phase2_policy_comparison_perimeter_p25_v1_summary_with_variability.csv` vs. `reports/phase2_osm_results.md`.
* **Confidence:** 100% Verified.

---

## 6. Issue 6: Canonical Metaflow Run ID Clarification

### Affected Files & Sections
* **File 1:** [`docs/phase2_runbook.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/docs/phase2_runbook.md#L47-L52)
* **File 2:** [`docs/phase2_artifact_viva_guide.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/docs/phase2_artifact_viva_guide.md#L23)

### Existing Statement
`docs/phase2_runbook.md` provides export commands for Metaflow run `1794405200312669` without clarifying that the `.metaflow/` directory was excluded from Git.

### Proposed Replacement Wording
> `Metaflow run 1794405200312669 is the canonical documented end-to-end training and validation run for the Phase 2 Hurdle model (SHA-256 167b523fc8c89199f6a8bf0689475272654db96b59b8a1da9b8a9986bff0b13b). Because Metaflow tracking was configured with local datastore (--metadata=local --datastore=local) and the .metaflow/ directory is gitignored, model registry inspection commands (python scripts/model_registry_report.py --run-id 1794405200312669) require importing the local .metaflow/ folder from the originating training workstation.`

### Evidence Verification & Confidence
* **Evidence:** Proven in Tasks B1, 4, and 11.
* **Confidence:** 100% Verified.

---

## 7. Remediation Application Readiness

| Item | Topic | Affected File | Status |
|---|---|---|---|
| **1** | Test Count (32 -> 34) | `docs/phase2_completion_report.md` | Replacement ready |
| **2** | DVC Scope Clarification | `docs/phase2_artifact_viva_guide.md` | Replacement ready |
| **3** | Docker Run Snippet Guard | `README.md`, `docs/phase2_runbook.md` | Replacement ready |
| **4** | CI & Deploy Telemetry | `README.md`, `docs/phase2_artifact_viva_guide.md` | Replacement ready |
| **5** | Legacy Grid Deprecation Banner | `reports/final_results_report.md` | Replacement ready |
| **6** | Canonical Metaflow Run Context | `docs/phase2_runbook.md` | Replacement ready |

**PLAN COMPLETE. NO FILES IN REPOSITORY MODIFIED.**

