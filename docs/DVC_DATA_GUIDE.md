# DVC Data Guide

The project's data is versioned with **DVC**. Git stores only small pointer files (`*.dvc`) that
name each data file and its MD5 fingerprint. The data itself lives in the team's **Google Drive**
folder (the DVC "remote", configured in `.dvc/config`).

| Pointer file | Data | Size |
|---|---|---|
| `data/sumo/queue_training_labels_v1.csv.dvc` | Training data of model v1 (18 SUMO runs) | 64 MB |
| `data/sumo/queue_training_labels_v2.csv.dvc` | v1 data + 12 surge runs (model v2, live) | 111 MB |
| `data/sumo/drift_surge_600.csv.dvc`, `drift_surge_720.csv.dvc` | Simulated production batches (demand surges) | 22 MB |
| `data/sumo/drift_sensor_fault_kmh.csv.dvc` | Synthetic sensor-fault batch | 26 MB |
| `sumo/bengaluru_osm/bengaluru_osm_sim.net.xml.dvc` | Road network used by every simulation | 242 MB |
| `sumo/bengaluru_osm/bengaluru_osm.net.xml.dvc` | Unsimplified network | 242 MB |
| `sumo/bengaluru_osm/bengaluru_osm_input.osm.dvc`, `planet_77.567,…osm.dvc` | OpenStreetMap extract (same file twice) | 176 MB |
| `data/raw/bangalore_traffic.csv.dvc` | Phase 1 historical dataset | 1.5 MB |

Do the [team setup](TEAM_SETUP.md) steps 1–3 first; they install DVC in `~/venvs/traffic-dvc`.
All commands below run in the **Ubuntu** window, inside the repository folder:

```bash
cd /mnt/c/Users/<your Windows name>/traffic-mlops
DVC=~/venvs/traffic-dvc/bin/dvc
```

---

## Part A: upload the data (the DVC teammate, once)

The data files were produced on Pranjali's laptop and must reach the remote once. Pranjali
gives you one file, **`TEAM_DATA_FOR_DVC.zip`** (95 MB), which contains all 10 files at their
repository paths.

1. **Get access to the Drive folder.** `.dvc/config` shows the remote as `gdrive://<folder id>`.
   The owner of that Google Drive folder (whoever set up DVC in Phase 1) shares it with your
   Google account as **Editor**.
2. **Unzip into the repository.** Right-click the zip → **Extract All…** → choose your
   `traffic-mlops` folder (the one that contains `dvc.yaml`). You should now have, for example,
   `traffic-mlops\data\sumo\queue_training_labels_v2.csv`.
3. **Upload.** Double-click **`team\windows\DVC_UPLOAD.cmd`**. It:
   - checks all 10 files against their pointer files (each must show **OK**; if any shows
     **CHANGED** or **missing**, stop and ask Pranjali for a new zip);
   - adds them to DVC's local cache without changing any pointer file;
   - uploads them. The first time, DVC prints a Google sign-in address and may open your
     browser: sign in with the account from step 1 and allow access. If Google says
     **"This app is blocked"**, do part B, then double-click `DVC_UPLOAD.cmd` again. Stop the
     Metaflow UI before signing in, because the sign-in page briefly uses port 8080;
   - finally compares your data with the remote. The last line must say the cache and the remote
     are **in sync**.
4. **Tell the team.** From now on `1_GET_DATA.cmd` works for everyone with access to the folder.

The commands it runs, if you prefer to type them (only the `*.dvc` data pointers are used as
targets, so the Phase 1 pipeline outputs in `dvc.yaml` are never touched):

```bash
mapfile -t T < <(~/venvs/traffic/bin/python scripts/team_helpers.py dvc-targets)
$DVC commit --force "${T[@]}"
$DVC push "${T[@]}"
$DVC status --cloud "${T[@]}"
```

Nothing in Git changes in this part, so there is nothing to commit.

## Part B: Google sign-in problems ("This app is blocked")

DVC's built-in Google sign-in is often refused by Google. The fix is your own (free) sign-in
client. It takes about 10 minutes, once per person:

1. Open https://console.cloud.google.com/ and create a project (any name, e.g. `traffic-dvc`).
2. **APIs & Services → Library**: search **Google Drive API** → **Enable**.
3. **APIs & Services → OAuth consent screen**: user type **External**, fill in the app name and
   your e-mail, and add your own Google account under **Test users**.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**: type
   **Desktop app**. Copy the **client ID** and **client secret**.
5. Store them **only on your computer** (the `--local` flag writes to `.dvc/config.local`, which
   Git ignores):
   ```bash
   $DVC remote modify myremote gdrive_client_id '<client ID>' --local
   $DVC remote modify myremote gdrive_client_secret '<client secret>' --local
   ```
6. Run `$DVC pull` (or `$DVC push`) again and sign in.

Never commit `.dvc/config.local`, never paste the client secret into chat, issues or PRs, and
never share it in screenshots.

## Part C: everyone else (download)

Double-click `team\windows\1_GET_DATA.cmd`. It runs `dvc pull`, then checks every file. Your
Google account needs at least **Viewer** access to the Drive folder. Sign-in problems: part B.

## Part D: adding or changing data later

New data is versioned like this (example: a new drift batch):

```bash
$DVC add data/sumo/drift_new_batch.csv            # writes data/sumo/drift_new_batch.csv.dvc
git add data/sumo/drift_new_batch.csv.dvc data/sumo/.gitignore
git commit -m "Add drift batch: <what it is>"
$DVC push data/sumo/drift_new_batch.csv.dvc       # upload the data
git push                                           # share the pointer, then open a PR
```

Rules:
- Run `git add`, `git commit` and `git push` in **PowerShell**, not in the Ubuntu window (Ubuntu's Git sees Windows line endings as changes).
- Never edit a data file in place. Create a new file (new name), so old results stay reproducible.
- Push the data (`dvc push`) **before** merging the PR that adds its pointer, or teammates' `dvc pull` fails.
- Record what the file is in `data/sumo/README.md` (rows, SHA-256, role).
