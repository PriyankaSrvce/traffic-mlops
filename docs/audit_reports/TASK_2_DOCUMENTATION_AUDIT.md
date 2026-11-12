# Task 2 — Read-Only Documentation Consistency Audit

**Audit Workspace:** [`D:\TrafficMLOps_Phase2_Workspace\repository`](file:///d:/TrafficMLOps_Phase2_Workspace/repository)  
**Date of Audit:** 2026-11-12T10:52:00+05:30  
**Auditor:** Senior MLOps Engineer & Technical Auditor  
**Investigation Mode:** Strictly Read-Only (Local Static Analysis & Evidence Cross-Referencing)

---

## 1. Executive Summary

An exhaustive, evidence-based consistency audit of all Phase 2 project documentation, reports, specifications, and runbooks was conducted against the actual codebase, Git history, test results, and live GitHub Actions telemetry.

### Major Findings Overview
1. **Missing Document:** The file `reports/phase2_render_deployment_20261111.md` requested in the audit specification **does not exist** anywhere in the repository or handoff packages.
2. **Test Count Discrepancy:** Multiple core documents (`docs/phase2_completion_report.md`, `docs/phase2_audit_report.md`, and handover notes) still state **32 tests passed**, conflicting with the current reality of **34 tests passing** established after commit `a85972c` added two model registry quality-gate tests.
3. **DVC Tracking False Claim:** `docs/phase2_artifact_viva_guide.md` explicitly calls the Phase 2 dataset a `"(DVC-managed payload, not in Git)"`. This is **unsupported and factually incorrect**; DVC tracks only Phase 1 data and raw OSM maps. The Phase 2 dataset has no `.dvc` pointer and is not in `dvc.yaml`.
4. **Unexecutable Runbook Commands:** Both `README.md` and `docs/phase2_runbook.md` provide copy-paste PowerShell commands referencing `.\models\bengaluru\bengaluru_queue_hurdle_v1_2026-11.joblib` without noting that the `models/` directory was excluded from Git and must be staged manually.
5. **Legacy Report Name Collision:** `reports/final_results_report.md` carries an authoritative title ("Final Experimental Results") but describes an obsolete 4x4 synthetic grid network and an older 300s/60s model (MAE 1.212 m), directly contradicting the current OSM corridor results in `reports/phase2_osm_results.md` (MAE 0.0550 m).
6. **Outdated CI/CD Status:** Core documentation states that the GitHub Actions deployment job has only ever been skipped on commit `a85972c` (Run `43036696130`). This is outdated; live GitHub Actions telemetry proves that on `main` at commit `d858900`, Run `43060494475` executed the deployment job via `workflow_dispatch` and passed in 37 seconds.

---

## 2. Missing Document Audit: `reports/phase2_render_deployment_20261111.md`

| Audit Item | Verification Result |
| :--- | :--- |
| **Requested File** | `reports/phase2_render_deployment_20261111.md` |
| **Filesystem Status** | **NON-EXISTENT** (Searched `repository/`, `handover/`, `teammate_handover_20261112/`, `D:\Mlops- traffic/`) |
| **Actual Evidence** | Render configuration exists in [`render.yaml`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/render.yaml). Deployment metadata exists in [`src/api/bengaluru_deployment_metadata.json`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/src/api/bengaluru_deployment_metadata.json). Local Docker smoke responses exist in [`reports/demo_smoke_20261111/`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/reports/demo_smoke_20261111/). |
| **Impact** | Anyone following an external audit checklist expecting a standalone Render deployment markdown report will encounter a missing file. |
| **Correction** | The repository documentation should either generate `reports/phase2_render_deployment_20261111.md` recording the live GitHub Actions Run `43060494475` deployment telemetry or update checklists to point directly to `reports/demo_smoke_20261111/README.md`. |

---

## 3. Detailed Issue-by-Issue Consistency Audit

```
========================================================================================================================
DOCUMENTATION INCONSISTENCY & CONTRADICTION MATRIX
========================================================================================================================
ID  Category               File & Section                       Existing Statement                    Defect Classification
------------------------------------------------------------------------------------------------------------------------
#1  Test Count             docs/phase2_completion_report.md §1  "passed locally: 32 tests"            OUTDATED (Now 34)
#2  Test Count             docs/phase2_audit_report.md §Commands "Python 3.12.6 full suite: 32 passed" OUTDATED (Now 34)
#3  DVC Tracking           docs/phase2_artifact_viva_guide.md §A19 "(DVC-managed payload, not in Git)" FACTUALLY INCORRECT
#4  DVC Procedure          docs/phase2_runbook.md §Data & Split "obtain them only through DVC"        MISLEADING / UNSUPPORTED
#5  Model Availability     README.md §API and Docker            "$model = (Resolve-Path .\models\...)" UNEXECUTABLE IN CHECKOUT
#6  Model Availability     docs/phase2_runbook.md §API Smoke    "Resolve-Path .\models\bengaluru\..." UNEXECUTABLE IN CHECKOUT
#7  Model Lineage / Hash   docs/phase2_audit_report.md §Evidence "Metaflow run 1794370252312711"      OUTDATED RUN CITATION
#8  CI / Deployment        docs/phase2_artifact_viva_guide.md §A33 "Run 43036696130... deploy skipped" OUTDATED (Run 43060494475 ran)
#9  Target / Metric Clash  reports/final_results_report.md §4-5 300s/60s grid models (MAE 1.212 m)    OBSOLETE CONFLICT
#10 Shared Registry Claim  scripts/model_registry_report.py §Doc "registry backed by Metaflow..."      AMBIGUOUS SCOPE
========================================================================================================================
```

---

### Issue #1: Test Count Discrepancy (32 vs. 34 Tests)
* **File & Section:** [`docs/phase2_completion_report.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/docs/phase2_completion_report.md#L11), Section 1 ("Completed and locally demonstrated").
* **Existing Statement:**  
  `"The full unittest suite passed locally: 32 tests, both in the extracted project and in a clean-checkout simulation without DVC data/model files."`
* **Why Outdated:**  
  In the same document (line 15) and in [`reports/phase2_verification_20261111.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/reports/phase2_verification_20261111.md#L10), the test count is recorded as **34 passed**. Commit `a85972c` added two new test cases to [`tests/test_model_registry.py`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/tests/test_model_registry.py#L30-L50): `test_registry_report_requires_matching_model_hash` and `test_registry_report_requires_exact_target_and_horizon`. Line 11 is an un-updated legacy statement.
* **Evidence Supporting Correction:**  
  Execution of `python -m unittest discover -s tests -v` runs **34 tests across 7 test files** (all passing).
* **Recommended Correction:**  
  Update line 11: `"The full unittest suite passed locally: 34 tests across 7 test files (including 4 model registry quality-gate tests)..."`

---

### Issue #2: Secondary 32-Test References in Audit Documentation
* **File & Section:** [`docs/phase2_audit_report.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/docs/phase2_audit_report.md#L44-L46), Section "Commands and checks performed".
* **Existing Statement:**  
  `"Python 3.12.6 full test suite in the extracted project: python -m unittest discover -s tests -v — 32 passed."`  
  `"Re-ran ... using Python 3.12.6 — 32 passed, 0 failed, 0 errors."`
* **Why Outdated:**  
  While lines 11, 23, and 70 of the same file mention 34 tests, lines 44-46 retain historical notes from the earlier validation pass prior to adding registry test coverage.
* **Evidence Supporting Correction:**  
  WSL Python 3.12.3 test discovery log: `Ran 34 tests in 0.284s - OK`.
* **Recommended Correction:**  
  Add historical context: `"Earlier validation pass passed 32 tests; subsequent addition of test_model_registry.py quality tests expanded the suite to 34 passing tests."`

---

### Issue #3: False Claim that Phase 2 Dataset is a "DVC-Managed Payload"
* **File & Section:** [`docs/phase2_artifact_viva_guide.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/docs/phase2_artifact_viva_guide.md#L19), Artifact Table.
* **Existing Statement:**  
  `"sumo/bengaluru_osm/datasets/osm_v2b/training_labels_incident_quarantined.csv (DVC-managed payload, not in Git) | The simulated training table used by the queue model."`
* **Why Factually Incorrect:**  
  The dataset `training_labels_incident_quarantined.csv` is **NOT managed by DVC**:
  1. No `.dvc` pointer file exists anywhere in `sumo/bengaluru_osm/datasets/`.
  2. [`dvc.yaml`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/dvc.yaml) and [`dvc.lock`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/dvc.lock) contain zero Phase 2 pipeline stages.
  3. The directory `sumo/bengaluru_osm/datasets/` is explicitly listed in [`.gitignore`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/.gitignore) as an unversioned local directory.
* **Evidence Supporting Correction:**  
  Inspection of `dvc.yaml` (contains only Phase 1 stages `featurize` and `train`) and Task B2 audit report [`reports/TASK_B2_INDEPENDENT_MODEL_RECOVERY_OPTIONS.md`](file:///d:/TrafficMLOps_Phase2_Workspace/reports/TASK_B2_INDEPENDENT_MODEL_RECOVERY_OPTIONS.md).
* **Recommended Correction:**  
  Change table entry to: `"sumo/bengaluru_osm/datasets/osm_v2b/training_labels_incident_quarantined.csv (Git-ignored simulation artifact, not tracked in DVC) | The simulated training table..."`

---

### Issue #4: Misleading DVC Recovery Instructions in Runbook
* **File & Section:** [`docs/phase2_runbook.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/docs/phase2_runbook.md#L27), Section "Data and split".
* **Existing Statement:**  
  `"If the files are DVC-managed, obtain them only through the team's reviewed DVC process. Do not copy model/data into Git."`
* **Why Misleading / Unsupported:**  
  Phrasing this as *"If the files are DVC-managed..."* leads teammates to believe that configuring DVC remote credentials will allow pulling the Phase 2 training dataset. As proven in Task B2, the Phase 2 training CSV was never added to DVC. Pulling DVC will only fetch raw Phase 1 data and raw OSM XMLs.
* **Evidence Supporting Correction:**  
  Output of `git status` and DVC files audit confirming zero Phase 2 tracking.
* **Recommended Correction:**  
  Update to: `"Note: Phase 2 simulation datasets and model binaries are NOT tracked in DVC; obtain them directly through the team's secure file transfer from the experimental scratch workspace."`

---

### Issue #5 & #6: Unexecutable Local Docker PowerShell Commands
* **Files & Sections:**  
  - [`README.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/README.md#L58-L66), Section "API and Docker" (L59)  
  - [`docs/phase2_runbook.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/docs/phase2_runbook.md#L61-L69), Section "API and local HTTP smoke test" (L62)
* **Existing Statement:**  
  ```powershell
  $model = (Resolve-Path .\models\bengaluru\bengaluru_queue_hurdle_v1_2026-11.joblib).Path
  docker run --rm -p 8000:8000 `
    --mount "type=bind,source=$model,target=/models/bengaluru_queue_hurdle_v1_2026-11.joblib,readonly" ...
  ```
* **Why Unexecutable in Checkout:**  
  If a teammate clones the repository and executes this command, PowerShell crashes immediately with:  
  `Resolve-Path : Cannot find path '...\models\bengaluru\bengaluru_queue_hurdle_v1_2026-11.joblib' because it does not exist.`  
  The `models/` directory is gitignored and was excluded from the repository. The command fails to document the prerequisite manual step of creating the directory and placing the file there.
* **Evidence Supporting Correction:**  
  Filesystem check: `repository\models: DOES NOT EXIST`.
* **Recommended Correction:**  
  Prepend prerequisite staging instructions:
  ```powershell
  # Prerequisite: Ensure the verified model binary is placed in models/bengaluru/
  if (-not (Test-Path .\models\bengaluru\bengaluru_queue_hurdle_v1_2026-11.joblib)) {
      Write-Error "Model binary missing. Obtain from teammate and stage in models/bengaluru/ first."
  }
  ```

---

### Issue #7: Conflicting Metaflow Run Citations Across Audit Documents
* **Files & Sections:**  
  - [`docs/phase2_audit_report.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/docs/phase2_audit_report.md#L30-L32), L30, L32, L71  
  - [`reports/phase2_osm_results.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/reports/phase2_osm_results.md#L34)  
  - [`reports/phase2_verification_20261111.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/reports/phase2_verification_20261111.md#L19)
* **Existing Statements:**  
  - `docs/phase2_audit_report.md` L32: cites run `1794370252312711`.  
  - `docs/phase2_audit_report.md` L30: cites runs `1794391865386585` and `1794393031537675`.  
  - `reports/phase2_verification_20261111.md` L19: cites run `1794405200312669`.
* **Why Contradictory / Confusing:**  
  Four distinct Metaflow run IDs are cited across different files as the "fresh" or "reproduced" run. All of them produced the same model hash (`167b523f...`), but having four different run IDs in documentation without a clear lineage chronology confuses examiners about which run is the definitive registry entry.
* **Evidence Supporting Correction:**  
  `reports/phase2_verification_20261111.md` confirms run `1794405200312669` is the final and latest run that persists `model_blob` as an artifact.
* **Recommended Correction:**  
  Harmonize all references to explicitly state: `"Initial validation runs: 1794391865386585 and 1794393031537675; Canonical final Metaflow run with full artifact-blob persistence: 1794405200312669."`

---

### Issue #8: Outdated CI/CD Deployment Status (Run 43036696130 vs. 43060494475)
* **Files & Sections:**  
  - [`README.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/README.md#L74), L74  
  - [`docs/phase2_artifact_viva_guide.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/docs/phase2_artifact_viva_guide.md#L33), L33  
  - [`docs/phase2_handoff_summary.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/docs/phase2_handoff_summary.md#L16), L16  
  - [`reports/phase2_verification_20261111.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/reports/phase2_verification_20261111.md#L38), L38
* **Existing Statement:**  
  `"Run 43036696130 passed on commit a85972c on branch phase2-completion-20261111; the deployment job was skipped. Deployment is a separate manual gate."`
* **Why Outdated:**  
  This documentation was written when only feature-branch run `43036696130` had been executed. Subsequent to those reports:
  1. Commit `d858900` was merged to `main`, triggering push Run `43039410684` (passed checks, deploy skipped).
  2. Manual `workflow_dispatch` Run `43060494475` was triggered on `main` at commit `d858900`, which **executed and passed the deployment job in 37 seconds**, polling `/health` and getting HTTP 200.
* **Evidence Supporting Correction:**  
  GitHub Actions REST API live query results verified in Task 2B audit.
* **Recommended Correction:**  
  Update documentation to include the completed main-branch deployment run: `"Feature branch CI verified in Run 43036696130. Main branch CI verified in Run 43039410684. Manual deployment workflow dispatch verified in Run 43060494475 (deploy job completed successfully in 37s)."`

---

### Issue #9: Obsolete Synthetic Grid Results in `reports/final_results_report.md`
* **File & Section:** [`reports/final_results_report.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/reports/final_results_report.md#L23-L68), Sections 3, 4, 5.
* **Existing Statement:**  
  Presents a 4x4 grid network with intersections B1, B2, C1, C2, and lists:
  - 300-second queue model: MAE 1.285 m (all targets), 3.380 m (positive queues).
  - 60-second queue model: MAE 1.212 m (all targets), 3.285 m (positive queues).
  - Controller results: fixed duration 89.68 s vs. predictive 83.56 s.
* **Why Severely Contradictory:**  
  This document is titled *"AI-Driven Adaptive Traffic Management Using a Digital Twin — Final Experimental Results"*. However, its metrics are from an early synthetic-grid pilot and completely contradict the final OSM Bengaluru corridor results in [`reports/phase2_osm_results.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/reports/phase2_osm_results.md) (held-out MAE 0.0550 m; positive queue MAE 2.1995 m; mean travel time 504.08 s vs 507.27 s).
* **Evidence Supporting Correction:**  
  `docs/phase2_handoff_summary.md` (L12) notes: *"The existing reports/final_results_report.md is preserved from the repository and contains older composite/grid experiment claims. Use reports/phase2_osm_results.md for current OSM model results."*
* **Recommended Correction:**  
  Add an explicit deprecation callout banner at the top of `reports/final_results_report.md`:
  `"> [!WARNING] HISTORICAL EXPERIMENT NOTICE: This report contains legacy preliminary metrics from an earlier 4x4 synthetic grid network. For authoritative Phase 2 Bengaluru OSM corridor results, refer exclusively to reports/phase2_osm_results.md."`

---

### Issue #10: Ambiguity Regarding "Model Registry" Capabilities
* **Files & Sections:**  
  - [`scripts/model_registry_report.py`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/scripts/model_registry_report.py#L1-L6), Module Docstring  
  - [`docs/phase2_execution_plan.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/docs/phase2_execution_plan.md#L46)
* **Existing Statement:**  
  `"The registry is backed by the configured Metaflow metadata/datastore... With the default local configuration it is machine-local; a shared registry requires a team-managed remote Metaflow datastore..."`
* **Why Risky / Needs Clarification:**  
  Course evaluators expecting a centralized model registry (like AWS SageMaker Model Registry, MLflow Registry, or Databricks) might fail the requirement if presented as a "Model Registry" without the disclaimer that it is a **local, file-backed Metaflow version catalog**.
* **Evidence Supporting Correction:**  
  `docs/phase2_audit_report.md` marks Model Registry as `PARTIALLY COMPLETE` specifically due to the lack of a shared hosted server.
* **Recommended Correction:**  
  Standardize the viva phrasing: always refer to it as a *"Local Metaflow-Backed Version Catalog and Quality Gating System"* rather than an enterprise shared registry service.

---

## 4. Cross-Document Thematic Consistency Summary

| Thematic Dimension | Documents in Agreement | Documents with Contradictions or Stale Statements | Final Ground Truth Reality |
| :--- | :--- | :--- | :--- |
| **Unit Test Suite** | `README.md`, `phase2_runbook.md`, `phase2_verification_20261111.md` (34 tests) | `phase2_completion_report.md`, `phase2_audit_report.md` (32 tests) | **34 unit tests pass** across 7 test files. |
| **DVC Scope** | `dvc.yaml`, `dvc.lock`, `phase2_osm_results.md` (Phase 1 only) | `phase2_artifact_viva_guide.md` (claims Phase 2 CSV is DVC-managed) | **DVC manages Phase 1 only.** Zero Phase 2 datasets are in DVC. |
| **Model Candidate Hash** | `bengaluru_deployment_metadata.json`, `app.py`, `Dockerfile` (`72bc...`) | `phase2_verification_20261111.md`, `bengaluru_queue_model_flow.py` (`167b...`) | Two distinct files exist. Option 1 approved to promote `167b...`. |
| **CI/CD Execution** | GitHub Actions API (Runs 43039410684 & 43060494475 passed on `main`) | `README.md`, `phase2_artifact_viva_guide.md` (cite only older feature-branch run) | **Main CI and manual deployment both passed** on commit `d858900`. |
| **Predictive Controller Claim** | All documents agree: predictive control is **not** superior to fixed/adaptive | None (Consistent academic honesty maintained) | In high flow, predictive control causes teleports; fixed-time equals or beats it. |
| **Target Variable & Units** | All documents agree: `queue_length_m_t_plus_60s` in **metres** | `sumo/label_queue_data_60s.py` had default name `_300s.csv` (fixed in commit `a85972c`) | Horizon is strictly **60 seconds**, unit is **metres**. |

---

## 5. Recommended Action Plan & Editorial Corrections

1. **Retain Clean Repository Guarantee:** No edits were applied during this audit; `repository/` remains 100% clean.
2. **Apply Non-Destructive Editorial Patch (Post-Approval):**
   * Update line 11 of `docs/phase2_completion_report.md` from 32 to 34 tests.
   * Remove `(DVC-managed payload, not in Git)` from line 19 of `docs/phase2_artifact_viva_guide.md`.
   * Add deprecation warning banner to `reports/final_results_report.md`.
   * Add existence check to PowerShell Docker run snippets in `README.md` and `docs/phase2_runbook.md`.
   * Add reference to main branch GitHub Actions Run `43060494475` in `README.md` and `docs/phase2_artifact_viva_guide.md`.
3. **Generate Missing Render Deployment Report:**  
   Author `reports/phase2_render_deployment_20261111.md` documenting the verified parameters of GitHub Actions Run `43060494475`.

---

## 6. Compliance & Integrity Confirmation

* **Files Modified in Repository:** Exactly **0** (Repository working tree on branch `main` is clean).
* **External Calls / Mutating Commands:** Exactly **0**.
* **Zero Fabrication:** All findings are derived strictly from inspected local files, Git commits, and verified API runs.

---
*Report completed and saved. Working tree remains clean.*

