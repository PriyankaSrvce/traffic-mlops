# Team launchers

Double-click launchers for Windows (`windows/`) and the WSL scripts they run (`wsl/`).
Start with [`docs/TEAM_SETUP.md`](../docs/TEAM_SETUP.md): steps 1-5, then any demo part.

| Order | Launcher | What it does |
|---|---|---|
| once | `0_SETUP_WSL.cmd` | Python environments, SUMO libraries, DVC (in WSL Ubuntu) |
| once | `1_GET_DATA.cmd` | Data via DVC (or unzipped `TEAM_DATA_FOR_DVC.zip`), checks, splits, model |
| check | `RUN_TESTS.cmd` | PyTest suite |
| demo | `START_MONITORING.cmd` / `RUN_LIVE_TRAFFIC.cmd` / `STOP_MONITORING.cmd` | API + Prometheus + Grafana, simulated traffic |
| demo | `RUN_DRIFT_CHECK.cmd` | Drift detector + Evidently + retraining trigger |
| once | `SETUP_METAFLOW_UI.cmd` | Metaflow UI source (pinned) + patch |
| demo | `START_METAFLOW_UI.cmd` / `RUN_TRAINING_FLOW.cmd` / `RUN_METAFLOW_GRAPHS.cmd` / `STOP_METAFLOW_UI.cmd` | Metaflow UI, training runs, results graphs |
| demo | `RUN_SUMO_DEMO.cmd` | SUMO map window with the model-driven controller |

Everything writes only to `outputs/`, `models/`, `data/sumo/splits*/` and `.metaflow-service/` (all git-ignored).
