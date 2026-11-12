# Task 5 — Phase 2 Artifact & DVC Reconciliation Report (Strict Read-Only)

**Workspace:** `D:\TrafficMLOps_Phase2_Workspace\`  
**Authoritative Repository:** [`D:\TrafficMLOps_Phase2_Workspace\repository`](file:///d:/TrafficMLOps_Phase2_Workspace/repository)  
**Current Git State:** Branch `main` @ Commit [`d85890058a13094ab3852f6297d87f29d5d01d0e`](file:///d:/TrafficMLOps_Phase2_Workspace/repository) (`working tree clean`)  
**Date of Audit:** 2026-11-12T11:15:00+05:30  
**Auditor:** Senior MLOps Engineer & Technical Auditor  
**Investigation Mode:** Strictly Read-Only (Local Filesystem, DVC Metadata, and Git Tracking Inspection)

---

## Executive Summary

An exhaustive, strictly read-only filesystem and metadata audit was conducted across the authoritative repository (`repository/`), the parent workspace (`D:\TrafficMLOps_Phase2_Workspace\`), and the handover packages (`handover/` and `teammate_handover_20261112/`).

This audit definitively resolves the documented contradictions regarding whether the Phase 2 simulation dataset, model binaries, Metaflow datastore, and DVC tracking exist locally.

---

## A. Dataset Availability

* **Target Dataset:** `sumo/bengaluru_osm/datasets/osm_v2b/training_labels_incident_quarantined.csv`
* **Status:** **BLOCKED / FILE ABSENT**

### Empirical Inspection Evidence:
1. **Filesystem Search:**
   - Path in `repository/`: `D:\TrafficMLOps_Phase2_Workspace\repository\sumo\bengaluru_osm\datasets\osm_v2b\training_labels_incident_quarantined.csv` $\to$ **Exists: False**
   - Path in `handover/`: `.../handover/traffic-mlops-phase2-handover/.../training_labels_incident_quarantined.csv` $\to$ **Exists: False**
   - Path in `teammate_handover_20261112/`: `.../teammate_handover_20261112/.../training_labels_incident_quarantined.csv` $\to$ **Exists: False**
   - Total files matching `training_labels*.csv` across entire workspace: **0**
2. **Git Tracking Status:**
   - Command: `git check-ignore -v sumo/bengaluru_osm/datasets/osm_v2b/training_labels_incident_quarantined.csv`
   - Output: `.gitignore:35:sumo/bengaluru_osm/datasets/` (Exit Code: 0)
   - Classification: **File absent, Git-ignored, mentioned in documentation but physically unavailable.**
3. **Documented Specifications (Reference Only):**
   - Rows: 357,124 labeled rows across 18 simulation runs
   - Expected SHA-256: `4e8213df71d3ed2df8bb2995ec195e1610f4398ad37f0e049a4399d9f93a5ffb`
   - Content inspection: **Cannot be inspected** because bytes do not exist on disk.

---

## B. Model Artifact Availability

* **Target Model 1 (API Candidate):** `models/bengaluru/bengaluru_queue_hurdle_v1_2026-11.joblib`
* **Target Model 2 (Metaflow Artifact):** `models/bengaluru/bengaluru_queue_hurdle_v1_2026-11_metaflow_1794405200312669.joblib`
* **Status:** **BLOCKED / FILE ABSENT**

### Empirical Inspection Evidence:
1. **Filesystem Search:**
   - `repository/models/bengaluru/bengaluru_queue_hurdle_v1_2026-11.joblib` $\to$ **Exists: False**
   - `repository/models/bengaluru/bengaluru_queue_hurdle_v1_2026-11_metaflow_1794405200312669.joblib` $\to$ **Exists: False**
   - Recursive search across entire workspace for any `.joblib`, `.pkl`, `.pt`, `.bin`, `.onnx` files $\to$ **0 model files found.**
2. **Git Tracking Status:**
   - Command: `git check-ignore -v models/bengaluru/bengaluru_queue_hurdle_v1_2026-11.joblib`
   - Output: `.gitignore:33:models/**/*.joblib` (Exit Code: 0)
   - Classification: **File absent, Git-ignored, mentioned in documentation but physically unavailable.**
3. **Cryptographic Hash Comparison:**
   - Documented API candidate hash: `72bc01ba9b659eeb47cd977b9bfb691e552da9f610bf637a96b05d3d36f9ea71`
   - Documented Metaflow canonical hash: `167b523fc8c89199f6a8bf0689475272654db96b59b8a1da9b8a9986bff0b13b`
   - Actual calculated hash: **Cannot be calculated** (physical binaries absent from storage).

---

## C. Metaflow Datastore Availability

* **Target Datastore:** `.metaflow/` directory
* **Status:** **BLOCKED / ABSENT**

### Empirical Inspection Evidence:
1. **Search Results Across All Locations:**
   - `repository/.metaflow/` $\to$ **Does not exist**
   - `D:\TrafficMLOps_Phase2_Workspace\.metaflow/` $\to$ **Does not exist**
   - `handover/.../.metaflow/` $\to$ **Does not exist**
   - `teammate_handover_20261112/.../.metaflow/` $\to$ **Does not exist**
   - Total `.metaflow` directories found across entire workspace: **0**
2. **Can Run `1794405200312669` be Recovered in Current Workspace?**
   - **NO.** Metaflow was executed locally (`--metadata=local --datastore=local`) on teammate Pranjali's machine (`work/phase2-completion-evidence-20261111/`).
   - Neither the step execution JSONs, nor the step artifacts, nor the serialized `model_blob` binary were committed to Git or included in handover archives.
   - Running `metaflow.Run("BengaluruQueueModelFlow/1794405200312669")` raises `MetaflowNotFound`.

---

## D. DVC Tracking Status

* **Status:** **VERIFIED**

### Empirical Inspection Evidence:
1. **Git-Tracked DVC Metadata Files in Repository:**
   - Command: `git ls-files *.dvc **/*.dvc dvc.yaml dvc.lock .dvc/config`
   - Output (8 files total):
     1. `.dvc/config` (Sanitized remote URL `gdrive://...`)
     2. `dvc.yaml` (Defines `featurize` and `train` stages)
     3. `dvc.lock` (Lock hashes for `featurize` and `train`)
     4. `data/raw/bangalore_traffic.csv.dvc` (Phase 1 tabular dataset pointer)
     5. `sumo/bengaluru_osm/bengaluru_osm.net.xml.dvc` (OSM network XML)
     6. `sumo/bengaluru_osm/bengaluru_osm_input.osm.dvc` (OSM input map)
     7. `sumo/bengaluru_osm/bengaluru_osm_sim.net.xml.dvc` (OSM simulation net)
     8. `sumo/bengaluru_osm/planet_77.567,12.882_77.693,12.958.osm.dvc` (OSM bounding-box extract)
2. **Four Critical Determinations:**
   - **Does Phase 2 dataset have a DVC pointer?** **NO.** There is no `.dvc` file for `training_labels_incident_quarantined.csv`.
   - **Does Phase 2 dataset have a DVC pipeline stage?** **NO.** In `dvc.yaml` and `dvc.lock`, only Phase 1 stages exist (`data/raw/bangalore_traffic.csv` $\to$ `data/processed/traffic_features.csv` $\to$ `model.pkl`).
   - **Is the pointer tracked by Git?** **N/A.** No pointer exists for Phase 2 data. (The four OpenStreetMap `.dvc` files in `sumo/bengaluru_osm/` are tracked by Git, but they track map geometry XML/OSM files, not simulation queue observations or hurdle models).
   - **Is only Phase 1 currently represented in DVC metadata?** **YES.** DVC tracks exclusively Phase 1 tabular data and OSM map payloads. Phase 2 queue modeling is 100% orchestrated by Metaflow outside of DVC.

---

## E. API Model Hash Verification

* **Status:** **PARTIALLY VERIFIED** (Configuration verified; execution blocked by absent binary)

### Empirical Inspection Evidence:
1. **Configured Expected Model SHA-256:**
   - `src/api/bengaluru_deployment_metadata.json`: `"sha256": "72bc01ba9b659eeb47cd977b9bfb691e552da9f610bf637a96b05d3d36f9ea71"`
   - `Dockerfile`: `ENV QUEUE_MODEL_SHA256=72bc01ba9b659eeb47cd977b9bfb691e552da9f610bf637a96b05d3d36f9ea71`
   - `render.yaml`: `QUEUE_MODEL_SHA256: 72bc01ba9b659eeb47cd977b9bfb691e552da9f610bf637a96b05d3d36f9ea71`
   - Alignment: **100% consistent across all deployment configuration files.**
2. **Configured Artifact Paths:**
   - `src/api/app.py`: `DEFAULT_MODEL = ROOT / "models" / "bengaluru" / "bengaluru_queue_hurdle_v1_2026-11.joblib"`
   - `Dockerfile`: `ENV QUEUE_MODEL_PATH=/models/bengaluru_queue_hurdle_v1_2026-11.joblib`
   - `render.yaml`: `value: /tmp/queue-model.joblib`
3. **Does the Configured Artifact Exist on Disk?**
   - **NO (File Absent).** Path `repository/models/bengaluru/bengaluru_queue_hurdle_v1_2026-11.joblib` does not exist.
4. **Does Actual File Hash Match Configured Hash?**
   - **BLOCKED.** Cannot compute cryptographic digest because the physical model file is absent from disk.
   - However, the pre-deserialization validation logic in `src/api/app.py` (L40–L65) is **VERIFIED**: it reads raw file bytes and invokes `hmac.compare_digest()` before calling `joblib.load()`.

---

## F. Reconciliation of Conflicts with Previous Reports

| Document / Report | Conflicting Statement | Ground Truth Verification Result |
| :--- | :--- | :--- |
| [`docs/phase2_artifact_viva_guide.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/docs/phase2_artifact_viva_guide.md#L19) (L19) | Labels Phase 2 dataset as `"(DVC-managed payload, not in Git)"`. | **False.** DVC has no pointer, no stage, and no cache for this file. It is an unversioned local simulation CSV. |
| [`docs/phase2_runbook.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/docs/phase2_runbook.md#L27) (L27) | States: `"If the files are DVC-managed, obtain them only through the team's reviewed DVC process."` | **Misleading.** Implies Phase 2 dataset can be fetched via DVC remote. In reality, DVC remote holds only Phase 1 and OSM maps. |
| [`README.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/README.md#L59) (L59) | Provides Docker command: `$model = (Resolve-Path .\models\bengaluru\bengaluru_queue_hurdle_v1_2026-11.joblib).Path`. | **Unexecutable in fresh clone.** `models/bengaluru/` does not exist. Model must be staged manually before running. |
| [`reports/phase2_render_deployment_20261111.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/reports) | Listed as an expected evidence file in Task 2 & Task 5 specifications. | **Non-existent.** No such file was ever committed to the repository. |
| Model Hash Divergence | API metadata pins `72bc...` while Metaflow run `1794405200312669` produced `167b...`. | **Two distinct local training runs.** Approved Option 1 will promote `167b...` once the binary is provided by teammate. |

---

## G. Overall Verdict

```
========================================================================================================================
FINAL AUDIT VERDICT TABLE
========================================================================================================================
Pillar                              Status              Summary of Ground Truth
------------------------------------------------------------------------------------------------------------------------
A. Dataset Availability             BLOCKED / ABSENT    File absent from storage; Git-ignored (.gitignore:35).
B. Model Artifact Availability      BLOCKED / ABSENT    Files absent from storage; Git-ignored (.gitignore:33).
C. Metaflow Datastore Availability  BLOCKED / ABSENT    .metaflow/ absent across workspace; run cannot be recovered locally.
D. DVC Tracking Status              VERIFIED            DVC tracks Phase 1 and OSM maps only. Zero Phase 2 DVC tracking.
E. API Model Hash Configuration     PARTIALLY VERIFIED  Configured consistently (72bc...); execution blocked by missing file.
F. Documentation Reconciliation     VERIFIED            All 5 major documentation contradictions identified and explained.
------------------------------------------------------------------------------------------------------------------------
OVERALL VERDICT: VERIFIED (READ-ONLY AUDIT RECONCILIATION COMPLETE; LIVE EXECUTION BLOCKED PENDING BINARY FILE)
========================================================================================================================
```

* **Compliance:** Zero files in `repository/` were edited, created, renamed, or deleted. Zero external operations were conducted.

