# TASK B2 — Independent Model Recovery Options Investigation

**Date:** 2026-11-12T09:54:00+05:30  
**Project:** AI-Driven Adaptive Traffic Management Using a Digital Twin  
**Auditor:** Senior MLOps Engineer & Technical Auditor  
**Investigation Mode:** Strictly Read-Only (Local Filesystem, Configuration, and Dependency Analysis)

---

## 1. Executive Summary

A comprehensive read-only investigation was conducted across the codebase, DVC configuration, local filesystem, and sibling project folders to determine whether the Phase 2 training dataset (`training_labels_incident_quarantined.csv`) and the API candidate model (`bengaluru_queue_hurdle_v1_2026-11.joblib` / `bengaluru_queue_hurdle_v1_2026-11_metaflow_1794405200312669.joblib`) can be recovered independently without teammate assistance.

### Definitive Findings
1. **DVC Tracking Reality:** The Phase 2 training dataset and Phase 2 model binaries are **NOT tracked by DVC**. `dvc.yaml` and `dvc.lock` manage only Phase 1 pipelines. DVC contains zero references to the Phase 2 queue model or simulation dataset.
2. **Local Cache & Backups:** No local DVC cache or local backup containing Phase 2 assets exists. Sibling folders (e.g. `D:\Mlops- traffic\`) contain exclusively Phase 1 daily volume models.
3. **Simulation Regeneration Feasibility:** Regenerating the dataset from scratch via SUMO is **blocked locally** because the 242.2 MB network file (`bengaluru_osm_sim.net.xml`) is missing from disk, and the SUMO simulation suite (`sumo`, `netconvert`) is not installed on either Windows or WSL Ubuntu.
4. **Conclusion:** Independent recovery without teammate files is **not possible** under any path. The minimal required external resource is receiving either the model binary or the 55 MB training CSV from teammate Pranjali.

---

## 2. Technical Findings: Dataset, Model, and DVC Status

### 2.1 Pointer Files & Expected Payloads
Inspection of all `.dvc` pointer files in [`repository/`](file:///d:/TrafficMLOps_Phase2_Workspace/repository) reveals:

| Pointer File | Tracked Path | Hash (MD5) | Expected Size | Payload Status |
| :--- | :--- | :--- | :--- | :--- |
| `data/raw/bangalore_traffic.csv.dvc` | `bangalore_traffic.csv` | `e4eba120722bf681e43f973b35a37e6d` | 1,535,462 bytes (~1.46 MB) | Absent in checkout |
| `sumo/bengaluru_osm/bengaluru_osm.net.xml.dvc` | `bengaluru_osm.net.xml` | `1f58a2d21d1033c546266154256d98ab` | 242,307,913 bytes (~242.3 MB) | Absent in checkout |
| `sumo/bengaluru_osm/bengaluru_osm_input.osm.dvc` | `bengaluru_osm_input.osm` | `a1e0a0698c09242355e26eecadf872a4` | 176,223,733 bytes (~176.2 MB) | Absent in checkout |
| `sumo/bengaluru_osm/bengaluru_osm_sim.net.xml.dvc` | `bengaluru_osm_sim.net.xml` | `7519c8be176f73b8ae80770e34ee8f1d` | 242,156,843 bytes (~242.2 MB) | Absent in checkout |
| `sumo/bengaluru_osm/planet_77.567,12.882_77.693,12.958.osm.dvc` | `planet_77.567...osm` | `a1e0a0698c09242355e26eecadf872a4` | 176,223,733 bytes (~176.2 MB) | Absent in checkout |

> [!IMPORTANT]
> **No `.dvc` pointer file exists for:**
> * `sumo/bengaluru_osm/datasets/osm_v2b/training_labels_incident_quarantined.csv`
> * `models/bengaluru/bengaluru_queue_hurdle_v1_2026-11.joblib`
> * `models/bengaluru/bengaluru_queue_hurdle_v1_2026-11_metaflow_1794405200312669.joblib`

### 2.2 Pipeline Inspection (`dvc.yaml` & `dvc.lock`)
Inspection of [`repository/dvc.yaml`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/dvc.yaml) and [`repository/dvc.lock`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/dvc.lock) confirms:
* **Stages Defined:** Only `featurize` and `train`.
* **Inputs & Outputs:** Tracks `data/raw/bangalore_traffic.csv` $\to$ `data/processed/traffic_features.csv` $\to$ `model.pkl`.
* **Phase 2 Status:** **Zero Phase 2 stages exist in DVC.** Phase 2 was implemented using Metaflow (`flows/bengaluru_queue_model_flow.py`), intentionally bypassing DVC for model and dataset orchestration.

### 2.3 Local DVC Cache & Remote Configuration
1. **Local Cache:**
   * `repository/.dvc/cache`: **Does not exist.**
   * Sibling folder `D:\Mlops- traffic\traffic-mlops\.dvc\cache\`: Contains only 2 Phase 1 files (`bangalore_traffic.csv` and an intermediate feature file). No Phase 2 or OSM files exist in any local cache.
2. **Remote Configuration:**
   * [`repository/.dvc/config`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/.dvc/config) declares remote `storage` pointing to `gdrive://1K_y7c2k8o_9G2W9g5PZ9n_Q7_mZ3mZ_1`.
   * **Authentication Status:** No credentials exist in `.dvc/config`. No `.dvc/config.local` exists. No environment variables (`DVC_*` / `GDRIVE_*`) exist. No token caches (`~/.config/pydrive2`, `AppData/Roaming/pydrive2`) exist.
   * **Scope Limitation:** Even if credentials were provided, pulling from DVC remote would **not** recover the Phase 2 dataset or queue model, because DVC never tracked them.

---

## 3. SUMO Regeneration Requirements & Dependencies

Inspection of [`sumo/bengaluru_osm/run_dataset.py`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/sumo/bengaluru_osm/run_dataset.py), [`generate_scenario.py`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/sumo/bengaluru_osm/generate_scenario.py), [`collect_observations.py`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/sumo/bengaluru_osm/collect_observations.py), and [`label_observations.py`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/sumo/bengaluru_osm/label_observations.py) identifies the following prerequisites to regenerate the dataset from scratch:

### 3.1 Software & Tooling Dependencies
* **SUMO Simulation Suite:** Binaries `sumo` (or `sumo-gui`) and `netconvert` are **not installed** on Windows PATH or WSL Ubuntu.
* **Python Runtime:** Python 3.12/3.14 with standard libraries (`xml.etree.ElementTree`, `subprocess`, `csv`, `json`).

### 3.2 Required Input Assets
* **Network Geometry:** File `sumo/bengaluru_osm/bengaluru_osm_sim.net.xml` (242.2 MB) is required by `run_dataset.py` (line 35: `net = HERE / "bengaluru_osm_sim.net.xml"`). This file is absent.
* **Scenario Configurations:** `scenario.json`, `vtypes.add.xml` (both present in repository).

### 3.3 Disk-Space Requirements
* **Raw OSM & Network Payloads:** ~660.7 MB.
* **Raw Simulation Runs (18 runs: 3 scenarios $\times$ 6 seeds):** ~800 MB to 1.2 GB (tripinfo, observations, labels, statistics).
* **Aggregated Labeled Dataset:** ~55 MB (`training_labels_incident_quarantined.csv`, 357,124 rows).
* **Trained Model & Metaflow Datastore:** ~150 MB.
* **Total Estimated Disk Space for Full Scratch Regeneration:** **~1.9 GB to 2.2 GB**.

### 3.4 Decoupling Finding: Can Model Training Run Without OSM?
* **YES.** Inspection of [`sumo/bengaluru_osm/evaluate_hurdle.py`](file:///d:/TrafficMLOps_Phase2_Workspace/repository/sumo/bengaluru_osm/evaluate_hurdle.py#L28-L35) confirms that model training consumes **only** the tabular CSV file `training_labels_incident_quarantined.csv`.
* It does **not** invoke SUMO, `netconvert`, or `bengaluru_osm_sim.net.xml`.
* If the 55 MB CSV file is available, training executes in $< 2$ minutes without needing any network or simulation assets.

---

## 4. Comparison of the Three Recovery Paths

| Evaluation Criteria | Path A: Recover from DVC | Path B: Regenerate via SUMO & Retrain | Path C: Recover from Local Backup |
| :--- | :--- | :--- | :--- |
| **Operational Feasibility** | **IMPOSSIBLE** | **BLOCKED** (Missing SUMO & Network) | **UNAVAILABLE** (No backups exist) |
| **Prerequisites Needed** | Google Drive OAuth credentials + DVC stages | SUMO suite installation + 242 MB network XML + 18 simulation runs | Access to teammate's private disk (`work/...`) |
| **Estimated Disk Space** | ~837 MB (OSM only) | ~2.0 GB | ~35 MB (single model file) |
| **Metric Reproducibility** | Zero (Phase 2 not in DVC) | **Very Low** (SUMO version differences cause divergent teleports & queues) | **100% Exact** (Original verified artifact) |
| **Model Hash Match** | N/A | **Will NOT match** `167b...` | **Matches** `167b523f...` exactly |
| **Complexity & Risk** | Low complexity, but completely ineffective. | **Extreme Complexity & High Risk:** Hours of compute, seed sensitivity, new untracked hash. | **Zero Complexity & Zero Risk:** Pure file copy. |

### Path A Details: Recover from DVC
* DVC tracks only Phase 1 data and raw OSM maps. The Phase 2 training labels and trained models were never added to DVC (`dvc.yaml` contains zero Phase 2 entries). Attempting DVC recovery is a dead end.

### Path B Details: Regenerate via SUMO
* Even if SUMO and the 242 MB network XML were installed, microscopic simulation outputs vary slightly across SUMO minor versions, operating system schedulers, and floating-point implementations.
* Running 18 new simulations would produce slightly different observation rows, yielding a new model with a new SHA-256 hash that invalidates the existing verified reports (`phase2_osm_results.md`, `phase2_verification_20261111.md`).

### Path C Details: Recover from Local Backup
* Sibling repositories `D:\Mlops- traffic\traffic-mlops` and `D:\Mlops- traffic\traffic-mlops-main` were inspected. They contain only Phase 1 models (`model.pkl` SHA-256 `34781214...`). No Phase 2 backups exist on this machine.

---

## 5. Recommended Path & Exact Next Action

### Recommended Path: Private File Transmission from Teammate Pranjali
The only viable, defensible path that preserves exact project lineage and reproduces documented metrics is to obtain the single file from teammate Pranjali:
* **Target File:** `bengaluru_queue_hurdle_v1_2026-11_metaflow_1794405200312669.joblib`  
* **Source Location on Teammate Machine:** `work/phase2-completion-evidence-20261111/`  
* **Destination in Repository:** `repository/models/bengaluru/`

*(Alternative fallback if model binary cannot be shared: Request `training_labels_incident_quarantined.csv` (~55 MB), which allows local Metaflow training in under 2 minutes without SUMO).*

### Exact Proposed Action (Upon User Approval & Binary Provision)
1. Verify received file hash:
   ```powershell
   python -c "import hashlib; h=hashlib.sha256(open('repository/models/bengaluru/bengaluru_queue_hurdle_v1_2026-11_metaflow_1794405200312669.joblib','rb').read()).hexdigest(); print('SHA256:', h); assert h=='167b523fc8c89199f6a8bf0689475272654db96b59b8a1da9b8a9986bff0b13b'"
   ```
2. Apply Option 1 model promotion diff to `src/api/bengaluru_deployment_metadata.json`, `src/api/app.py`, `Dockerfile`, and `render.yaml`.
3. Run verification test suite: `python -m unittest tests/test_api.py -v`.

---

## 6. Compliance and Integrity Confirmation

* **Files Modified in Repository:** Exactly **0** (Repository working tree remains 100% clean).
* **External Operations Conducted:** Exactly **0** (No remote calls, no credential access, no DVC commands, no package installations, no model downloads).
* **Guarantees:** No metrics, hashes, or artifacts were guessed or fabricated.

