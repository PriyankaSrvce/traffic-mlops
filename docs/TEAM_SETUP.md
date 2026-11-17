# Team Setup Guide: run the whole project on your own laptop

This guide is for every team member. Follow it once, from top to bottom, and you can run
everything that is shown in the demo: tests, the SUMO simulation, Metaflow training and UI,
drift checks with Evidently, the monitoring stack with Prometheus and Grafana, and the web
dashboard.

Written for **Windows 10/11**. Every step is a double-click or a copy-paste.
Time needed: about 1 hour the first time, mostly waiting for downloads.

> One team member also takes over the **data upload to DVC**. That person follows
> [`DVC_DATA_GUIDE.md`](DVC_DATA_GUIDE.md), part A, once. Until then, everyone else can still get
> the data as a zip file (step 4, option B).

---

## What you will be able to run

| What | How | Needs |
|---|---|---|
| Live dashboard, Evidently reports, API docs | Open https://traffic-queue-api.onrender.com/dashboard | Nothing (a browser) |
| CI/CD runs | https://github.com/PriyankaSrvce/traffic-mlops/actions | Nothing |
| Test suite (PyTest) | `team\windows\RUN_TESTS.cmd` | Steps 1–4 |
| Drift check: PSI + Evidently + retraining trigger | `RUN_DRIFT_CHECK.cmd` | Steps 1–4 |
| API + Prometheus + Grafana, with live traffic | `START_MONITORING.cmd`, then `RUN_LIVE_TRAFFIC.cmd` | Docker (data only for live traffic) |
| Metaflow training runs, Metaflow UI, results graphs | `SETUP_METAFLOW_UI.cmd` (once), `START_METAFLOW_UI.cmd`, `RUN_TRAINING_FLOW.cmd`, `RUN_METAFLOW_GRAPHS.cmd` | Steps 1–4 + Docker |
| SUMO simulation window with the model controlling the signals | `RUN_SUMO_DEMO.cmd` | Steps 1–4, Windows 11 |

All launchers are in the `team\windows` folder of the repository.

---

## Step 1: Install three programs (once)

1. **Git for Windows**: https://git-scm.com/download/win. Keep all default options.
2. **WSL with Ubuntu 24.04** (a Linux inside Windows; the project's Python tools run there):
   - Press the Windows key, type **PowerShell**, right-click it, choose **Run as administrator**.
   - Run:
     ```powershell
     wsl --install -d Ubuntu-24.04
     ```
   - Restart the laptop when asked. An **Ubuntu** window opens and asks for a new **username**
     and **password**. Choose any, and remember the password: setup asks for it once.
   - If you already have Ubuntu in WSL, check its version with `wsl -l -v`. Ubuntu 24.04 is needed for the pinned Python 3.12.
3. **Docker Desktop**: https://www.docker.com/products/docker-desktop/. Keep "Use WSL 2"
   ticked. Open it once and wait until the bottom-left says **Engine running**.

## Step 2: Get the code

Open **PowerShell** (normal, not administrator) and run:

```powershell
cd $HOME
git clone https://github.com/PriyankaSrvce/traffic-mlops.git
```

This creates `C:\Users\<your name>\traffic-mlops`. Open that folder in File Explorer, then the
`team\windows` folder inside it. Every launcher below is in that folder.

If you already have a clone, update it instead: `cd $HOME\traffic-mlops` and then `git pull`.

## Step 3: One-time setup

Double-click **`0_SETUP_WSL.cmd`**.

- It asks for your **Ubuntu password** once, to install a few system libraries for SUMO's window.
- It then builds three Python environments with exactly the versions the project was verified
  with: the main one, one for Evidently, and one for DVC. This takes 5–15 minutes.
- It finishes with a version list and **"Setup complete"**.

Running it again later is safe: it only installs what is missing.

## Step 4: Get the data and the model

The data (SUMO datasets and the road network, about 900 MB) is versioned with **DVC**. The
model files are downloaded from GitHub and checked against their SHA-256 fingerprint.

**Option A: with DVC (normal way, once the DVC teammate has uploaded the data)**

Double-click **`1_GET_DATA.cmd`**.

- The first time, a Google sign-in link appears. Sign in with a Google account that has
  access to the team's DVC folder. If you see **"This app is blocked"**, follow
  [`DVC_DATA_GUIDE.md`](DVC_DATA_GUIDE.md), part B.
- It downloads the data, checks every file against its DVC fingerprint, builds the
  train/validation/test splits, and downloads the production model.

**Option B: from the zip file (if DVC is not ready yet)**

1. Ask the DVC teammate for **`TEAM_DATA_FOR_DVC.zip`** (95 MB).
2. Right-click it → **Extract All…** → choose your **`traffic-mlops`** folder → Extract.
   The files must land in `traffic-mlops\data\sumo\` and `traffic-mlops\sumo\bengaluru_osm\`.
3. Double-click **`1_GET_DATA.cmd`**. It sees the data, skips the download and does the rest.

The result must show **OK** for all 10 files and end with **"Data and model ready."**

## Step 5: Check that everything works

Double-click **`RUN_TESTS.cmd`**. It must end with **`66 passed`** (or more) and no failures.

---

## Running each part of the demo

### Monitoring: API + Prometheus + Grafana + live traffic (about 7 minutes)

1. Start **Docker Desktop**, wait for **Engine running**.
2. Double-click **`START_MONITORING.cmd`**. The first time it builds the API image (2–5 minutes).
   Grafana (http://localhost:3000) and the web dashboard (http://localhost:8000/dashboard) open.
   The API downloads the production model by itself and refuses to start if the fingerprint is wrong.
3. Double-click **`RUN_LIVE_TRAFFIC.cmd`** and keep its window open. It sends normal traffic,
   then a demand surge, then a faulty speed sensor, for about 5 minutes. Watch Grafana:
   - mean input speed jumps from about 3 to about 10 m/s in the last phase (sensor fault);
   - the model's live error rises during the surge and stays below the baseline's.
4. When finished, double-click **`STOP_MONITORING.cmd`**.

### Drift check with Evidently and the retraining trigger (about 3 minutes)

Double-click **`RUN_DRIFT_CHECK.cmd`**. It prints a verdict for each of 5 batches, writes Evidently
HTML reports and shows the retraining trigger's decision. It also prints a folder path: open it
in File Explorer and double-click any `*_occupied_lanes.html` file to see the Evidently report.

### Metaflow: training runs, UI and graphs

1. Once: double-click **`SETUP_METAFLOW_UI.cmd`** (downloads the Metaflow UI source and applies
   the project's small patch).
2. Start Docker Desktop, then double-click **`START_METAFLOW_UI.cmd`**. The first time builds
   images (5–10 minutes). The UI opens at http://localhost:8083 (empty at first).
3. Double-click **`RUN_TRAINING_FLOW.cmd`**. It trains v1 and v2 (1–2 minutes each). At the end it
   checks whether your runs **reproduced the registered models exactly** (same SHA-256):
   `167b523f…` for v1 and `8da60b0e…` for v2. Refresh the UI to see the runs, their steps and artifacts.
4. Double-click **`RUN_METAFLOW_GRAPHS.cmd`** and keep it open. Open http://localhost:8325. In the
   drop-down at the top, choose the **last** `end/…` entry: that is the card with the charts
   (the other entries show each step's code).
5. When finished, double-click **`STOP_METAFLOW_UI.cmd`**. Your runs are kept for next time.

### SUMO simulation window (Windows 11)

Double-click **`RUN_SUMO_DEMO.cmd`**. After 30–60 seconds the SUMO window opens on the Bengaluru
corridor and the production model controls the signals (predictive policy). If you see
"No WSL display", run `wsl --shutdown` in PowerShell and try again.

### Phase 1 (MLflow)

See [`phase1_reproduction_guide.md`](phase1_reproduction_guide.md). The historical CSV comes with the
same `1_GET_DATA.cmd` (`data/raw/bangalore_traffic.csv`).

---

## Team operations: who does what, step by step

These tasks used to be done on one laptop only. Anyone with the access listed can do them.

| Task | Access needed |
|---|---|
| Change code, open PRs | GitHub write access to `PriyankaSrvce/traffic-mlops` |
| Deploy the website | GitHub write access (the deploy job runs in GitHub Actions) |
| Switch or roll back the live model | GitHub write access **and** access to the Render service (ask the Render workspace owner to invite you: Render → workspace menu → **Invite your team**) |
| Upload or update data | Editor access to the team's DVC Google Drive folder ([`DVC_DATA_GUIDE.md`](DVC_DATA_GUIDE.md)) |

### Change code (always this way)

```powershell
cd $HOME\traffic-mlops
git checkout main
git pull
git checkout -b phase3-<short-topic>
# edit files, then RUN_TESTS.cmd must pass
git add <the files you changed>
git commit -m "Say what changed and why"
git push -u origin phase3-<short-topic>
```

Open the link Git prints to create a pull request. Wait for the green check
(GitHub Actions) and a teammate's review, then merge. Branch names starting with `phase3-`
also run CI on every push.

### Deploy the website after a merge

1. GitHub → **Actions** → **Phase 2 CI** → **Run workflow** (grey button on the right).
2. Branch **main**, **tick** "Trigger Render deployment to the protected production environment".
3. Click **Run workflow**. Both jobs must turn green (about 3 minutes); Render then rebuilds (about 3 more).
4. Check https://traffic-queue-api.onrender.com/api/v1/model-info. The `model_sha256` must be the registry's production entry.

A merge alone never changes the live site; auto-deploy is off on purpose (governance).

### Switch the live model (promote a new version, or roll back)

The live model is chosen by its SHA-256. Changing it means changing the fingerprint in four
places, the same way v2 was promoted (see that commit on `main`):

1. **Publish the model file** at an HTTPS address. For a new model: GitHub → Releases → new release
   with the `.joblib` as an asset. For a rollback: the address already exists. Run
   `~/venvs/traffic/bin/python scripts/model_promotion.py rollback` in WSL; it prints both values.
2. **In a branch**, put the new SHA-256 in `Dockerfile`, `render.yaml` and
   `src/api/bengaluru_deployment_metadata.json`, and the new address in
   `monitoring/docker-compose.yml`. Update `registry/model_versions.json`: the new model gets
   `"stage": "production"`, the old one `"archived"` with `"rollback_target": true`.
   `RUN_TESTS.cmd` fails if these places disagree.
3. PR → green CI → review → merge.
4. **Render** → service `traffic-queue-api` → **Environment** → **Edit**: set `QUEUE_MODEL_URL` and
   `QUEUE_MODEL_SHA256` → **Save only** (not "Save and deploy").
5. Deploy the website (above) and check `/api/v1/model-info` shows the new SHA-256.

If the address and fingerprint do not match, the new server refuses to start and the old one
keeps running, so a mistake cannot take the site down with a wrong model.

### Retrain after drift

```bash
# in the Ubuntu window, inside the repository folder (e.g. cd /mnt/c/Users/<you>/traffic-mlops)
bash team/wsl/drift_check.sh                 # writes outputs/drift_check/drift_report.json
~/venvs/traffic/bin/python scripts/retraining_trigger.py --drift-report outputs/drift_check/drift_report.json \
    --execute --dataset data/sumo/queue_training_labels_v2.csv --artifact-root outputs/metaflow_artifacts
```

The trigger trains only when a **performance** alert exists. A new model then needs
`scripts/model_promotion.py compare` (see `docs/GOVERNANCE.md` §4.4) and human approval
before it may be switched live (above).

---

## Troubleshooting

| Problem | Fix |
|---|---|
| A launcher window flashes and closes | Run it from PowerShell to read the message: `cmd /c team\windows\<NAME>.cmd` |
| `wsl` not found, or "Please enable Virtual Machine Platform" | Redo step 1 (WSL) and restart; virtualization must be on in the BIOS |
| `docker` not found / "Docker failed" | Start Docker Desktop and wait for **Engine running** |
| Port already in use (8000, 3000, 8080, 8083, 9000) | Something else is running there: stop the other stack (`STOP_MONITORING.cmd`, `STOP_METAFLOW_UI.cmd`) or restart Docker Desktop |
| `dvc pull` asks to sign in / "This app is blocked" | [`DVC_DATA_GUIDE.md`](DVC_DATA_GUIDE.md), part B |
| `1_GET_DATA.cmd` shows **CHANGED** for a file | The file is not the versioned one. Delete it and run `1_GET_DATA.cmd` again |
| Training run says "NOT a registered model" | Your environment differs from the pinned one. Re-run `0_SETUP_WSL.cmd`; do not upgrade packages by hand |
| SUMO: "No WSL display" | PowerShell: `wsl --shutdown`, wait 10 s, try again (Windows 11 needed for the window) |
| Live site slow or 502 at first | The free server sleeps; open the page, wait 60 s, refresh |
