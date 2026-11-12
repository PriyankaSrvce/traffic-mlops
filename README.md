# AI-Driven Adaptive Traffic Management Using a Digital Twin

## Current project status

This repository contains two distinct ML tasks:

1. **Phase 1 historical baseline:** predicts same-day daily `Traffic Volume` from the historical Bangalore CSV. Its unit is unspecified, and the dataset license remains unverified.
2. **Phase 2 SUMO prototype:** uses an OpenStreetMap-derived Bengaluru corridor and synthetic SUMO scenarios to predict lane queue length 60 seconds ahead and compare fixed-time, adaptive, and predictive signal policies. This is simulated evidence, not calibrated real-world traffic performance.

The OSM scenario generator defines two-wheelers, cars, auto-rickshaws, buses, and trucks. It uses two assumed fleet profiles (balanced: 55/25/12/4/4%; motorcycle-heavy: 68/18/9/3/2%) and seed-controlled random departure times across a 900-second window. The current labeled dataset records both the assumed profile and lane-level vehicle-type counts when vehicles are present. This is departure-time spread, not a separately modeled driver reaction/startup delay. Fleet shares are assumptions, not measured Bengaluru proportions.

The current Bengaluru queue model uses a held-out seed evaluation. Its reported aggregate MAE/RMSE/R² are 0.0550 m / 0.5135 m / 0.8836 versus persistence at 0.0694 m / 0.6513 m / 0.8127 (112,176 identical test rows). On the 2,753 rows with positive future queues, MAE/RMSE are 2.1995 m / 3.2369 m. On those same rows persistence scores MAE/RMSE 1.9020 m / 3.4377 m, so the model has a **higher MAE** (+15.6 %) but a lower RMSE (−5.8 %) than persistence there. Most of the aggregate gain comes from the 97.55 % zero-future rows, where persistence keeps predicting queues that have already cleared. On rows with a queue now or 60 s later (3,357), model MAE is 1.832 m vs 2.318 m for persistence. The target is sparse, so report all of these together. Recomputed 2026-11-12; see [the 2026-11-12 verification](reports/phase2_verification_20261112.md).

The predictive controller is implemented and has paired experiment results. In the clean low-demand runs (3 seeds) fixed-time had the lowest mean travel time (504.08 s vs 507.61 s adaptive, 507.27 s predictive) and the lowest mean waiting time (120.53 s vs 124.15 s / 123.63 s). Adaptive and predictive were within about 0.5 s of each other. The clean medium-300 batch also favoured fixed-time (531.30 / 536.10 / 536.74 s). Other medium and high runs have teleports/collisions and are quality failures. Do not claim that predictive control is best or that results generalize to real roads.

The latest local verification record is [`reports/phase2_verification_20261111.md`](reports/phase2_verification_20261111.md). It separates freshly verified local results from still-unverified GitHub CI, remote DVC, and hosted deployment steps.

## Architecture and important files

| Component | Main files |
|---|---|
| SUMO OSM corridor, data collection and controller | `sumo/bengaluru_osm/` |
| 60-second queue model training/evaluation | `sumo/bengaluru_osm/evaluate_hurdle.py`, `flows/bengaluru_queue_model_flow.py` |
| Separate earlier queue model flow | `flows/queue_model_flow.py` |
| API and prediction contracts | `src/api/app.py`, `src/api/bengaluru_deployment_metadata.json` |
| Offline prediction monitoring and feedback | `sumo/bengaluru_osm/monitoring.py`, `sumo/bengaluru_osm/record_feedback.py` |
| Unit tests | `tests/` (run with `unittest`) |
| DVC pipeline and pointers | `dvc.yaml`, `dvc.lock`, `*.dvc` |
| Reports and run instructions | `docs/`, `reports/` |

The model named by the API metadata is the Metaflow run `1794405200312669` artifact, SHA-256 `167b523fc8c89199f6a8bf0689475272654db96b59b8a1da9b8a9986bff0b13b`. The pinned WSL environment reproduced it byte-for-byte on 2026-11-12. The earlier deployment candidate (SHA-256 `72bc01ba9b659eeb47cd977b9bfb691e552da9f610bf637a96b05d3d36f9ea71`) is a separately serialized file. Its predictions on all 112,176 test rows match `167b` to within 7.1e-15 m, but its bytes differ, so it will not pass the `167b` integrity check. Model binaries are excluded from the source tree and build image; provide the exact `167b` file through an approved, SHA-256-verified artifact source or read-only mount.

## Setup and verification

Use Python 3.12. The pinned API dependencies are in `requirements-api.txt`; Phase 2/Metaflow dependencies are in `requirements-phase2.txt`. SUMO is a separate system dependency for simulations. Do not install the full Phase 1 requirements just to run the API tests.

```bash
python -m pip install -r requirements-phase2.txt -r requirements-test-phase1.txt
python -m unittest discover -s tests -v
```

The latest suite run used WSL Ubuntu / Python 3.12.3 and the pinned Phase 2 dependencies plus the Phase 1 test extras: **34 tests passed, 0 failed, 0 errors**. The earlier clean-checkout run passed 32 tests before two Metaflow registry tests were added. Neither local run means GitHub Actions passed. See the [audit report](docs/phase2_audit_report.md) and [latest verification](reports/phase2_verification_20261111.md).

The Bengaluru Metaflow graph check and fresh end-to-end training runs passed in WSL/Linux. Latest run `1794405200312669` used 357,124 labels and wrote the model bytes, SHA-256, dataset provenance, validation/test metrics, and eligibility record into Metaflow artifacts. The Metaflow-backed local registry verified the artifact hash and exported it successfully. Its model binary and run data remain outside this source contribution. Metaflow is run from Linux/WSL in this setup.

## API and Docker

API endpoints: `/api/v1/health`, `/api/v1/model-info`, `/api/v1/predict` (also available without `/api/v1`). The prediction target is `queue_length_m_t_plus_60s`, in metres, with 11 current-state features. A local live HTTP smoke test returned healthy status, the expected model SHA, and a finite prediction using the mounted candidate artifact.

Build the image:

```bash
docker build -t traffic-queue-api:local .
```

Run it with an approved local model mount (PowerShell example):

The model binary is gitignored, so stage the `167b` file first. It can be exported from the Metaflow run with `scripts/model_registry_report.py` or taken from the team's verified handover package:

```powershell
$modelPath = ".\models\bengaluru\bengaluru_queue_hurdle_v1_2026-11.joblib"
if (-not (Test-Path $modelPath)) { throw "Stage the 167b model at $modelPath first (it is not in Git)." }
if ((Get-FileHash $modelPath -Algorithm SHA256).Hash -ne "167B523FC8C89199F6A8BF0689475272654DB96B59B8A1DA9B8A9986BFF0B13B") { throw "Wrong model file." }
$model = (Resolve-Path $modelPath).Path
docker run --rm -p 8000:8000 `
  --mount "type=bind,source=$model,target=/models/bengaluru_queue_hurdle_v1_2026-11.joblib,readonly" `
  traffic-queue-api:local
```

The image's environment already points to the mounted path, the baked-in metadata and the `167b` SHA-256. If the configured hash does not match the file, startup is refused (the entrypoint exits with an error). If no file is mounted, the endpoints return HTTP 503.

History: on 2026-11-11 the image `traffic-queue-api:phase2-final` was built and run locally against the earlier `72bc…` candidate. Health, model-info and prediction returned HTTP 200, and a held-out example returned 5.1657 m against an observed 11.0 m. On 2026-11-12 the `167b` model returned the same 5.1656687762 m for that request through the API and the image entrypoint, but no container was built that day because the local Docker engine was unavailable. No image has been pushed.

## Metaflow, DVC and CI/CD

Metaflow is used for orchestration and local model artifacts; `scripts/model_registry_report.py` verifies eligible runs and can export a hash-verified artifact. The registry is local in this setup; no shared hosted Metaflow datastore has been established. A local `dvc status` found the raw CSV, processed CSV, `model.pkl`, and OSM/network outputs absent from this checkout/cache. No remote comparison, pull, or push was performed. The branch's sanitized tracked remote entry has no private authentication; remote availability remains unverified. Do not rely on DVC runs until the missing payload and lock/pipeline state are reconciled.

`.github/workflows/phase2-ci.yml` runs tests, Python compilation, Metaflow graph checks, and a Docker build on `main`, `phase2-*` branch pushes, and pull requests. Deployment is a manual, main-only workflow dispatch gated on successful checks. GitHub Actions runs (checked through the GitHub API on 2026-11-12):
- [43036696130](https://github.com/PriyankaSrvce/traffic-mlops/actions/runs/43036696130) passed on the feature branch (`a85972c`), with deploy skipped.
- [43039410684](https://github.com/PriyankaSrvce/traffic-mlops/actions/runs/43039410684) passed on `main` (`d858900`), with deploy skipped.
- [43060494475](https://github.com/PriyankaSrvce/traffic-mlops/actions/runs/43060494475), a manual dispatch on `main` (`d858900`), passed checks and its deploy job (37 s).

Review [the verification report](reports/phase2_verification_20261112.md) and [artifact viva guide](docs/phase2_artifact_viva_guide.md).

Render is the selected deployment platform because a Docker-based blueprint is already present. Automatic deployment is disabled so only the gated workflow can trigger it. In run 43060494475 the deploy step succeeded. Under this workflow, which fails when the deploy secrets are missing, success means the deploy-hook POST succeeded and the polling loop saw HTTP 200 from `$RENDER_SERVICE_URL/health`. The job log needs a GitHub login and has not been reviewed. The service URL is not recorded in this repository, and no hosted `/model-info` or `/predict` response has been captured, so hosted inference is **not verified**. That deployment was configured with the earlier `72bc…` hash. After this promotion, the file served by `QUEUE_MODEL_URL` must be replaced with the `167b` artifact before the next deploy, or the service will refuse to start.

## Reproduction and reports

- [Phase 2 runbook](docs/phase2_runbook.md)
- [Local Phase 2 API demo guide](docs/phase2_demo_guide.md)
- [OSM and simulation methodology](docs/bengaluru_osm_geographical_twin.md)
- [Current OSM queue-model results](reports/phase2_osm_results.md)
- [Phase 2 handoff summary](docs/phase2_handoff_summary.md)
- [Phase 2 requirement-by-requirement audit](docs/phase2_audit_report.md)

All simulation demand, fleet mixes, and converted signal timing are assumptions. OSM supplies road geography, not measured traffic volumes, fleet shares, origin-destination demand, or field signal plans. The historical dataset is not used as real-time arrivals. No live traffic signals or public roads are controlled.
