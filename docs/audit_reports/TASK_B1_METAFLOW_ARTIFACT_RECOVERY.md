# TASK B1 — Metaflow Artifact Recovery Investigation Report

**Investigation Date:** 2026-11-12T08:33:00+05:30  
**Project:** AI-Driven Adaptive Traffic Management Using a Digital Twin  
**Auditor:** Senior MLOps Engineer & Technical Auditor  
**Investigation Mode:** Strictly Read-Only (Local Filesystem & Static Analysis)

---

## 1. Executive Summary

An exhaustive, strictly read-only local forensic investigation was conducted to determine whether the original serialized model artifact from **Metaflow Run `1794405200312669`** (expected SHA-256: `167b523fc8c89199f6a8bf0689475272654db96b59b8a1da9b8a9986bff0b13b`) or the **API Candidate Model** (expected SHA-256: `72bc01ba9b659eeb47cd977b9bfb691e552da9f610bf637a96b05d3d36f9ea71`) can be recovered or reconstructed locally without teammate assistance or retraining.

### Definitive Conclusion
* **Is original recovery possible locally without teammate assistance?** **NO.**
* **Is local reconstruction or retraining possible without teammate assistance?** **NO.**
* **Root Cause:** As explicitly declared in project documentation (`reference/PHASE2_DETAILED_HANDOFF_AND_AI_PROMPT.md` and `reports/phase2_verification_20261111.md`), the handover packages (`handover/` and `teammate_handover_20261112/`) and the Git repository (`repository/`) were intentionally assembled as source-and-evidence distributions that exclude heavy binary artifacts (raw/processed datasets, `.joblib` model binaries, local `.metaflow` datastores, and private credentials).
* **Missing Asset:** The physical binary `bengaluru_queue_hurdle_v1_2026-11_metaflow_1794405200312669.joblib` and its parent `.metaflow` datastore reside on teammate Pranjali's machine in `work/phase2-completion-evidence-20261111/` and were never transmitted to this workstation.

---

## 2. Locations Inspected

The following local locations and environments were forensically searched for `.metaflow`, `.metaflowconfig`, run ID `1794405200312669`, hashes `167b523f...` and `72bc01ba...`, and any `.joblib` or `.pkl` binaries:

| # | Inspection Path / Environment | Scope & Method | Result |
| :--- | :--- | :--- | :--- |
| **1** | `D:\TrafficMLOps_Phase2_Workspace\repository` | Full recursive walk; hidden dirs, `models/`, `reports/`, `flows/`, `.git/` | No `.metaflow`, no `models/` directory, 0 `.joblib` / `.pkl` files found. Run ID and hash exist only in documentation text. |
| **2** | `D:\TrafficMLOps_Phase2_Workspace\handover\traffic-mlops-phase2-handover` | Full recursive walk of initial handover snapshot | No `.metaflow`, no `models/`, 0 model binaries. Hash `72bc...` present in docs only. |
| **3** | `D:\TrafficMLOps_Phase2_Workspace\teammate_handover_20261112\traffic-mlops-phase2-handover` | Full recursive walk of new teammate handover | Identical to (2); no `.metaflow`, no `models/`, 0 model binaries. |
| **4** | `C:\Users\Prajwal` | Windows user profile, `.metaflow`, `.metaflowconfig`, `Downloads`, `Documents\Codex` | `C:\Users\Prajwal\Documents\Codex` is empty (0 items). No Metaflow directories exist. |
| **5** | WSL Ubuntu 24.04 (`/home/prajwal`, `/tmp`, `/var/tmp`) | Linux subsystem filesystem search via `find` | No `.metaflow`, no `.metaflowconfig`, no matching run IDs or artifacts. |
| **6** | `D:\Mlops- traffic\traffic-mlops` | Sibling Phase 1 workspace (`mlruns/`, `mlflow.db`, `model.pkl`) | Contains Phase 1 daily volume models (`model.pkl` SHA-256 `34781214...`). Zero Phase 2 or Metaflow assets. |
| **7** | `D:\Mlops- traffic\traffic-mlops-main` | Sibling Phase 1 main checkout | Phase 1 assets only; zero Phase 2 or Metaflow assets. |

---

## 3. Files and Artifacts Status

### 3.1 Artifacts Status Matrix

| Artifact / File | Expected Location | Expected SHA-256 | Local Status |
| :--- | :--- | :--- | :--- |
| **Metaflow Datastore** | `.metaflow/` | N/A (Directory tree) | **MISSING** across all drives/workspaces |
| **Metaflow Model Binary** | `models/bengaluru/...joblib` | `167b523fc8c89199f6a8bf0689475272654db96b59b8a1da9b8a9986bff0b13b` | **MISSING** locally |
| **Metaflow Model Metadata** | `models/...json` | N/A | **MISSING** locally (captured only in report text) |
| **API Candidate Model** | `models/bengaluru/bengaluru_queue_hurdle_v1_2026-11.joblib` | `72bc01ba9b659eeb47cd977b9bfb691e552da9f610bf637a96b05d3d36f9ea71` | **MISSING** locally |
| **Training Labels Dataset** | `sumo/bengaluru_osm/datasets/osm_v2b/training_labels_incident_quarantined.csv` | `4e8213df71d3ed2df8bb2995ec195e1610f4398ad37f0e049a4399d9f93a5ffb` | **MISSING** locally ($N=357,124$) |
| **Metaflow Flow Code** | `flows/bengaluru_queue_model_flow.py` | N/A | **VERIFIED PRESENT** in `repository/` |
| **Registry Inspection Tool** | `scripts/model_registry_report.py` | N/A | **VERIFIED PRESENT** in `repository/` |
| **API Deployment Metadata** | `src/api/bengaluru_deployment_metadata.json` | N/A | **VERIFIED PRESENT** (pins `72bc...`) |
| **Unit Test Suite** | `tests/test_model_registry.py` | N/A | **VERIFIED PRESENT** (all 4 tests pass) |

---

## 4. Technical Analysis of Recovery Mechanisms

### 4.1 Datastore Configuration Expected by Project
Inspection of [`flows/bengaluru_queue_model_flow.py`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/flows/bengaluru_queue_model_flow.py#L20-L31) and [`reports/phase2_verification_20261111.md`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/reports/phase2_verification_20261111.md#L47-L55) reveals:
* Parameter `artifact-root` defaults to `ROOT / "reports" / "metaflow" / "bengaluru"`.
* The verified CLI invocation explicitly passed `--metadata=local --datastore=local`.
* **No Remote Datastore Exists:** The codebase does not configure AWS S3, Google Cloud Storage, or an HTTP Metaflow metadata service. Local datastore mode stores run data exclusively in a local `.metaflow/` directory relative to the runner's execution path.
* Because the run was performed on teammate Pranjali's computer (`work/phase2-completion-evidence-20261111/`), the `.metaflow` folder was generated on her private disk and never transferred.

### 4.2 Can the Artifact be Reconstructed from an Existing Model Blob?
* **No.** There is zero serialized model binary (`.joblib` or `.pkl`) for the queue hurdle model on this machine.
* In Python/Metaflow, `self.model_blob = model_path.read_bytes()` stores the exact byte array of the trained model file. Without the original bytes or the `.metaflow` artifact store, reconstruction of the exact byte sequence is impossible.

### 4.3 Can the Registry Export Logic be Used?
* Inspection of [`scripts/model_registry_report.py`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/scripts/model_registry_report.py#L119-L143) shows that `export_metaflow_model()` invokes `Run("BengaluruQueueModelFlow/1794405200312669")` and reads `run.data.model_blob`.
* Because `Run()` queries the local Metaflow metadata provider, executing this without the local `.metaflow` directory raises a `MetaflowNotFound` exception.
* Therefore, the export utility cannot be used until the `.metaflow` directory or the exported binary is placed on disk.

### 4.4 Would Retraining be Necessary or Sufficient?
* **Is Retraining Locally Possible Now?** **NO.** The input dataset `training_labels_incident_quarantined.csv` (SHA-256 `4e8213df...`, 357,124 rows) is also absent locally.
* **Would Retraining Reproduce SHA-256 `167b523f...`?** **UNLIKELY.** Even with the identical dataset and random seeds, serialized `joblib` objects encapsulate internal scikit-learn tree data structures and metadata that can vary across minor Python/C-extension compilation differences. Retraining would produce a *new* valid model with a *new* SHA-256 and a *new* Metaflow run ID, invalidating the existing documented run `1794405200312669`.

---

## 5. Distinction: Missing vs. Inaccessible Remote Artifacts

| Category | Artifact | Reason for Non-Availability |
| :--- | :--- | :--- |
| **Locally Missing** | `bengaluru_queue_hurdle_v1_...joblib` (`167b...`) | Excluded from Git and ZIP archives; resides on teammate's workstation. |
| **Locally Missing** | `bengaluru_queue_hurdle_v1_2026-11.joblib` (`72bc...`) | Prototype deployment binary excluded from Git and ZIP archives. |
| **Locally Missing** | `.metaflow/` datastore directory | Generated locally on teammate machine; excluded from Git/ZIP. |
| **Locally Missing** | `training_labels_incident_quarantined.csv` | Heavy DVC dataset payload excluded from Git/ZIP. |
| **Inaccessible Remote** | Remote Metaflow Service / S3 | **Does not exist.** The project architecture uses local Metaflow only. |
| **Inaccessible Remote** | DVC Remote (`gdrive://...`) | Tracks Phase 1 data only; OAuth credentials were securely purged in commit `81256d3`. Does not track Phase 2 Metaflow models. |
| **Inaccessible Remote** | Render Hosted Endpoint | `render.yaml` defines a blueprint with placeholder `QUEUE_MODEL_URL`; no public release or model bucket has been published. |

---

## 6. Recommended Next Actions

1. **Request the Specific Binary from Teammate Pranjali:**
   * Teammate needs to provide ONLY the following single file from her local workspace:
     `work/phase2-completion-evidence-20261111/.../bengaluru_queue_hurdle_v1_2026-11_metaflow_1794405200312669.joblib`  
     (or the archived `.metaflow/` directory).
2. **Execute Independent Cryptographic Verification:**
   * Upon receiving the file, place it in `repository/models/bengaluru/`.
   * Verify its SHA-256 matches `167b523fc8c89199f6a8bf0689475272654db96b59b8a1da9b8a9986bff0b13b`.
3. **Execute Task B Option 1 Promotion:**
   * Apply the approved lineage update to `bengaluru_deployment_metadata.json`, `app.py`, `Dockerfile`, and `render.yaml`.
   * Execute `python -m unittest tests/test_api.py -v` to confirm complete integration.

---

## 7. Compliance and Integrity Confirmation

* **Files Modified in Repository:** Exactly **0** (Repository working tree remains 100% clean).
* **External Operations Conducted:** Exactly **0** (No remote calls, no credential access, no DVC commands, no package installations, no model downloads).
* **Guarantees:** No metrics, hashes, or artifacts were guessed or fabricated.

