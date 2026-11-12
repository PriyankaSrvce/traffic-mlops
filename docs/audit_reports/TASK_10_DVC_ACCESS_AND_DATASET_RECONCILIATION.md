# TASK 10 — DVC ACCESS AND MISSING DATASET RECONCILIATION

**Authoritative Repository:** `D:\TrafficMLOps_Phase2_Workspace\repository`  
**Inspected Branch & Commit:** `main` @ `d85890058a13094ab3852f6297d87f29d5d01d0e`  
**Audit Protocol:** Strictly read-only; no downloads or pulls, no remote calls, no credentials requested or displayed, and zero file modifications.

---

## 1. DVC Configuration and Pipeline Metadata

Inspection of `.dvc/config`, `dvc.yaml`, `dvc.lock`, and repository `.dvc` pointer files:

### A. Remote Configuration (`.dvc/config`)
```ini
[core]
    remote = myremote
['remote "myremote"']
    url = gdrive://1myDKXQIrZpOoom4EmBiiH31vRZhuOCdl
```
* **Remote Type:** Google Drive (`gdrive://`).
* **Storage Location:** Target Google Drive folder ID `1myDKXQIrZpOoom4EmBiiH31vRZhuOCdl`.
* **Sanitization Status:** Commit `81256d3` purged all private service accounts and tokens from `.dvc/config`. No local credentials exist in `.dvc/config.local` (file is absent).

### B. Pipeline Stage Scope (`dvc.yaml` & `dvc.lock`)
* `dvc.yaml` defines exactly **two stages**:
  1. `featurize`: Converts `data/raw/bangalore_traffic.csv` + `src/features/bangalore_events.csv` $\rightarrow$ `data/processed/traffic_features.csv`.
  2. `train`: Trains `src/models/train.py` on `data/processed/traffic_features.csv` $\rightarrow$ `model.pkl`.
* **Scope Finding:** The pipeline definition in `dvc.yaml` and `dvc.lock` belongs **100% to Phase 1 (citywide daily traffic volume)**. There are **zero Phase 2 stages** in `dvc.yaml`.

### C. Git-Tracked `.dvc` Pointer Files
The repository contains exactly **five `.dvc` files**:

| Pointer File Path | Payload Filename | Payload MD5 Hash | Payload Size | Project Phase |
|---|---|---|---:|---|
| `data/raw/bangalore_traffic.csv.dvc` | `bangalore_traffic.csv` | `e4eba120722bf681e43f973b35a37e6d` | 1,535,462 bytes (~1.5 MB) | **Phase 1** |
| `sumo/bengaluru_osm/bengaluru_osm_sim.net.xml.dvc` | `bengaluru_osm_sim.net.xml` | `7519c8be176f73b8ae80770e34ee8f1d` | 242,156,843 bytes (~242 MB) | **Phase 2 (SUMO)** |
| `sumo/bengaluru_osm/bengaluru_osm.net.xml.dvc` | `bengaluru_osm.net.xml` | `1f58a2d21d1033c546266154256d98ab` | 242,307,913 bytes (~242 MB) | **Phase 2 (Raw Net)** |
| `sumo/bengaluru_osm/bengaluru_osm_input.osm.dvc` | `bengaluru_osm_input.osm` | `a1e0a0698c09242355e26eecadf872a4` | 176,223,733 bytes (~176 MB) | **Phase 2 (Raw OSM)** |
| `sumo/bengaluru_osm/planet_77.567,12.882_77.693,12.958.osm.dvc` | `planet_77.567,12.882...osm` | `a1e0a0698c09242355e26eecadf872a4` | 176,223,733 bytes (~176 MB) | **Phase 2 (Extract)** |

---

## 2. Investigation of the Phase 2 Training Dataset

Forensic audit of `sumo/bengaluru_osm/datasets/osm_v2b/training_labels_incident_quarantined.csv`:

1. **Pointer File Existence:**
   * `training_labels_incident_quarantined.csv.dvc` **DOES NOT EXIST** in the current checkout.
   * A full Git history search (`git log --all --full-history -- '*training_labels*.dvc'`) confirms that **no DVC pointer for this dataset has ever been committed to this repository**.
2. **Pipeline Stage Existence:**
   * Neither `dvc.yaml` nor `dvc.lock` contains any stage, dependency, or output referencing `training_labels_incident_quarantined.csv` or anything in `sumo/bengaluru_osm/datasets/`.
3. **Workspace & Handover Audit:**
   * The teammate handover directory (`teammate_handover_20261112`) was searched; it also contains zero DVC pointer files for the dataset.
4. **Definitive Conclusion:**
   * **The Phase 2 simulation dataset is completely untracked by DVC.** Any documentation describing it as a *"DVC-managed payload"* is factually incorrect. Even with full DVC remote access, `dvc pull` **cannot** retrieve this dataset because DVC has no content hash or record for it.

---

## 3. Investigation of SUMO Network and Demo Assets

Audit of the inputs required to run the SUMO microscopic simulation demo (`sumo/bengaluru_osm/demo.sumocfg`):

```xml
<configuration>
    <input>
        <net-file value="bengaluru_osm_sim.net.xml"/>
        <route-files value="traffic.rou.xml"/>
        <additional-files value="vtypes.add.xml"/>
    </input>
    ...
</configuration>
```

| Demo Asset / Input | File Path | Git Status | DVC Status | Local File Status |
|---|---|---|---|---|
| **Road Network Geometry** | `sumo/bengaluru_osm/bengaluru_osm_sim.net.xml` | Gitignored (`*.net.xml`) | **Tracked** via `.dvc` pointer (MD5 `7519c8be...`, 242 MB) | **Absent** (Payload missing locally) |
| **Corridor Route Flows** | `sumo/bengaluru_osm/traffic.rou.xml` | **Git-tracked** (13.2 KB) | Not in DVC | **Present** on disk |
| **Vehicle Class Archetypes**| `sumo/bengaluru_osm/vtypes.add.xml` | **Git-tracked** (1.5 KB) | Not in DVC | **Present** on disk |
| **Scenario Definition** | `sumo/bengaluru_osm/scenario.json` | **Git-tracked** (1.7 KB) | Not in DVC | **Present** on disk |
| **Predictive Model Binary** | `models/bengaluru/bengaluru_queue_hurdle_v1_2026-11.joblib` | Gitignored (`*.joblib`) | **Not tracked** (No `.dvc` file) | **Absent** on disk |

* **Network Retrievability:** Because `bengaluru_osm_sim.net.xml.dvc` is tracked in Git, the 242 MB network geometry file **is legitimately stored in DVC** and could be pulled if the Google Drive remote holds the payload.
* **Controller Demo Blocker:** While the routes and vehicle types are present in Git, running the predictive controller requires the model `.joblib` binary, which is **not tracked by DVC**.

---

## 4. Credential and Access Prerequisites

Inspection of local system and remote authentication requirements:

1. **Local DVC Installation Status:**
   * `dvc` executable is **NOT on Windows PATH** (`shutil.which('dvc')` returned `None`).
   * `dvc` Python package is **NOT installed** in the active Python environment.
   * `dvc` is **NOT installed** in the WSL Linux distribution (`wsl which dvc` exited 1).
2. **Remote Authentication Method:**
   * URL schema `gdrive://1myDKXQIrZpOoom4EmBiiH31vRZhuOCdl` requires the `dvc[gdrive]` extension (backed by `pydrive2`).
   * Google Drive remotes authenticate via **interactive OAuth 2.0 Web Flow**:
     * When `dvc pull` is invoked, it launches a local web server and instructs the user to log in via browser with an authorized Google account.
     * The granted OAuth refresh token is saved locally to `~/.config/pydrive2fs/` (or `~/.dvc/cache`).
3. **Current Machine Configuration:**
   * Neither `~/.config/pydrive2fs/` nor `~/.dvc/` exists on this machine.
   * The current workspace possesses **zero credentials, tokens, or permissions** for Google Drive folder `1myDKXQIrZpOoom4EmBiiH31vRZhuOCdl`.
4. **Authorized Account Prerequisite:**
   * To successfully pull from this remote, the user must log into a Google Account that has been explicitly granted **Viewer** or **Editor** permissions to Google Drive folder `1myDKXQIrZpOoom4EmBiiH31vRZhuOCdl` by the folder owner (teammate Priyanka).

---

## 5. Reconciliation Matrix: Retrievable vs. Non-Retrievable Assets

```
                                  [CURRENT REPOSITORY ASSETS]
                                               |
         +-------------------------------------+-------------------------------------+
         |                                                                           |
[POTENTIALLY RETRIEVABLE VIA DVC]                                       [CANNOT BE RETRIEVED VIA DVC]
(Has valid Git-tracked .dvc pointers)                                   (Zero DVC metadata or tracking)
         |                                                                           |
  1. bengaluru_osm_sim.net.xml (242 MB)                                  1. Phase 2 Dataset (357,124 rows)
     (Left-hand simulation network)                                         training_labels_incident_quarantined.csv
  2. bengaluru_osm.net.xml (242 MB)                                      2. Dataset Splits (train/val/test CSVs)
     (Raw converted OSM network)                                         3. API Candidate Model Binary (.joblib)
  3. bengaluru_osm_input.osm (176 MB)                                       bengaluru_queue_hurdle_v1_2026-11.joblib
  4. planet_77.567,12.882...osm (176 MB)                                 4. Metaflow Canonical Model (.joblib)
  5. Phase 1 bangalore_traffic.csv (1.5 MB)                              5. Metaflow Datastore (.metaflow/)
  6. Phase 1 traffic_features.csv (dvc.lock)                             6. Offline Test Predictions CSV
  7. Phase 1 model.pkl (dvc.lock)
```

---

## 6. Final Evaluation Report

### A. DVC Configuration Status: `VALID BUT UNAUTHENTICATED`
* `.dvc/config` defines a valid Google Drive remote (`gdrive://1myDKXQIrZpOoom4EmBiiH31vRZhuOCdl`).
* Credentials have been properly purged from Git. Local environment lacks DVC binaries and OAuth authorization tokens.

### B. Phase 2 CSV Tracking Status: `NOT TRACKED IN DVC`
* `training_labels_incident_quarantined.csv` has zero DVC pointer files, zero `dvc.yaml` stages, and zero Git history entries. It cannot be recovered through DVC.

### C. SUMO Network Tracking Status: `TRACKED IN DVC`
* The left-hand simulation network `bengaluru_osm_sim.net.xml` is tracked by a valid Git pointer (`sumo/bengaluru_osm/bengaluru_osm_sim.net.xml.dvc`, MD5 `7519c8be...`).

### D. Demo Asset Availability: `PARTIALLY AVAILABLE`
* Traffic routes (`traffic.rou.xml`) and vehicle types (`vtypes.add.xml`) are committed in Git.
* Network geometry (`bengaluru_osm_sim.net.xml`) requires DVC pull.
* Predictive model binary (`*.joblib`) is absent from both Git and DVC.

### E. Authentication Prerequisites: `GOOGLE OAUTH REQUIRED`
* To test remote pull, the user must install `dvc[gdrive]`, ensure their Google account has access to folder `1myDKXQIrZpOoom4EmBiiH31vRZhuOCdl`, and authenticate via OAuth.

### F. Exact Files Potentially Retrievable Through DVC:
1. `sumo/bengaluru_osm/bengaluru_osm_sim.net.xml` (242,156,843 bytes)
2. `sumo/bengaluru_osm/bengaluru_osm.net.xml` (242,307,913 bytes)
3. `sumo/bengaluru_osm/bengaluru_osm_input.osm` (176,223,733 bytes)
4. `sumo/bengaluru_osm/planet_77.567,12.882_77.693,12.958.osm` (176,223,733 bytes)
5. `data/raw/bangalore_traffic.csv` (1,535,462 bytes)
6. `data/processed/traffic_features.csv` (581,735 bytes, via `dvc.lock`)
7. `model.pkl` (4,083 bytes, via `dvc.lock`)

### G. Files That Cannot Be Retrieved Through DVC:
1. `sumo/bengaluru_osm/datasets/osm_v2b/training_labels_incident_quarantined.csv` (105 MB)
2. `sumo/bengaluru_osm/datasets/osm_v2b/splits/{train,val,test}.csv`
3. `models/bengaluru/bengaluru_queue_hurdle_v1_2026-11.joblib` (API candidate model)
4. `bengaluru_queue_hurdle_v1_2026-11_metaflow_1794405200312669.joblib` (Metaflow model)
5. `.metaflow/` directory
6. `sumo/bengaluru_osm/datasets/osm_v2b/hurdle_evaluation/test_predictions.csv`

---

## 7. Recommended Next Action

Do not attempt a DVC pull expecting to recover the Phase 2 training dataset or model binary: **they are not in DVC**.

1. **For the Phase 2 Model & Dataset:**
   Obtain `bengaluru_queue_hurdle_v1_2026-11_metaflow_1794405200312669.joblib` (SHA-256 `167b523f...`) and `training_labels_incident_quarantined.csv` directly from teammate Pranjali's local directory (`work/phase2-completion-evidence-20261111/`).
2. **For the SUMO Network Geometry (`bengaluru_osm_sim.net.xml`):**
   If simulation execution is desired, request read permission to Google Drive folder `1myDKXQIrZpOoom4EmBiiH31vRZhuOCdl`, or simply copy `bengaluru_osm_sim.net.xml` directly from Pranjali's workstation.
3. **For Project Documentation:**
   Execute the Task 9 documentation patch to delete the false claim in `docs/phase2_artifact_viva_guide.md` asserting that the Phase 2 dataset is DVC-managed.

**STOP. NO REMOTE CALLS OR FILE MUTATIONS PERFORMED.**

