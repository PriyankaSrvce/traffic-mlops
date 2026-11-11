# AI-Driven Adaptive Traffic Management Using a Digital Twin

## Current project status

This repository contains two distinct ML tasks:

1. **Phase 1 historical baseline:** predicts same-day daily `Traffic Volume` from the historical Bangalore CSV. Its unit is unspecified, and the dataset license remains unverified.
2. **Phase 2 SUMO prototype:** uses an OpenStreetMap-derived Bengaluru corridor and synthetic SUMO scenarios to predict lane queue length 60 seconds ahead and compare fixed-time, adaptive, and predictive signal policies. This is simulated evidence, not calibrated real-world traffic performance.

The OSM scenario generator defines two-wheelers, cars, auto-rickshaws, buses, and trucks. It uses two assumed fleet profiles (balanced: 55/25/12/4/4%; motorcycle-heavy: 68/18/9/3/2%) and seed-controlled random departure times across a 900-second window. The current labeled dataset records both the assumed profile and lane-level vehicle-type counts when vehicles are present. This is departure-time spread, not a separately modeled driver reaction/startup delay. Fleet shares are assumptions, not measured Bengaluru proportions.

The current Bengaluru queue model uses a held-out seed evaluation. Its reported aggregate MAE/RMSE/R² are 0.0550 m / 0.5135 m / 0.8836 versus persistence at 0.0694 m / 0.6513 m / 0.8127 (112,176 identical test rows). On the 2,753 rows with positive future queues, MAE/RMSE are 2.1995 m / 3.2369 m. The target is sparse, so both results matter. See [the current OSM results report](reports/phase2_osm_results.md) and [the audit](docs/phase2_audit_report.md).

The predictive controller is implemented and has paired experiment results. Available clean low-demand runs show adaptive control outperforming predictive control on mean trip, waiting, and time-loss metrics; some medium/high runs have teleports/collisions and are quality failures. Do not claim that predictive control is best or that results generalize to real roads.

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

The deployment candidate described by the API metadata is `models/bengaluru/bengaluru_queue_hurdle_v1_2026-11.joblib` with SHA-256 `72bc01ba9b659eeb47cd977b9bfb691e552da9f610bf637a96b05d3d36f9ea71`. It is intentionally excluded from the source tree/build image; provide it through an approved, SHA-256-verified artifact source or read-only mount. A distinct Metaflow run model has a different hash and must not be confused with this candidate.

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

```powershell
$model = (Resolve-Path .\models\bengaluru\bengaluru_queue_hurdle_v1_2026-11.joblib).Path
docker run --rm -p 8000:8000 `
  --mount "type=bind,source=$model,target=/models/bengaluru_queue_hurdle_v1_2026-11.joblib,readonly" `
  -e QUEUE_MODEL_PATH=/models/bengaluru_queue_hurdle_v1_2026-11.joblib `
  -e QUEUE_MODEL_METADATA_PATH=/app/src/api/bengaluru_deployment_metadata.json `
  -e QUEUE_MODEL_SHA256=72bc01ba9b659eeb47cd977b9bfb691e552da9f610bf637a96b05d3d36f9ea71 `
  traffic-queue-api:local
```

The image `traffic-queue-api:phase2-final` was built and run locally against the deployment candidate (SHA-256 `72bc01ba9b659eeb47cd977b9bfb691e552da9f610bf637a96b05d3d36f9ea71`) mounted read-only. Health, model-info, and prediction all returned HTTP 200. A held-out positive-queue example returned 5.1657 m against an observed 11.0 m label; it is one illustrative row, not a performance summary. The container ran as `apiuser` and was removed after checks. The fresh Metaflow model (SHA-256 `167b523fc8c89199f6a8bf0689475272654db96b59b8a1da9b8a9986bff0b13b`) is a separate registered artifact. No image was pushed and no public deployment occurred.

## Metaflow, DVC and CI/CD

Metaflow is used for orchestration and local model artifacts; `scripts/model_registry_report.py` verifies eligible runs and can export a hash-verified artifact. The registry is local in this setup; no shared hosted Metaflow datastore has been established. A local `dvc status` found the raw CSV, processed CSV, `model.pkl`, and OSM/network outputs absent from this checkout/cache. No remote comparison, pull, or push was performed. The branch's sanitized tracked remote entry has no private authentication; remote availability remains unverified. Do not rely on DVC runs until the missing payload and lock/pipeline state are reconciled.

`.github/workflows/phase2-ci.yml` runs tests, Python compilation, Metaflow graph checks, and a Docker build on `main`, `phase2-*` branch pushes, and pull requests. Deployment is a manual, main-only workflow dispatch gated on successful checks. The latest local checks passed, but GitHub Actions has not run on this branch yet. Review [the latest verification report](reports/phase2_verification_20261111.md).

Render is the selected deployment platform because a Docker-based blueprint is already present. Automatic deployment is disabled so only the gated workflow can trigger it. A Render service, stable HTTPS model URL, Render deploy hook, and service URL have not been configured; no public deployment is claimed.

## Reproduction and reports

- [Phase 2 runbook](docs/phase2_runbook.md)
- [Local Phase 2 API demo guide](docs/phase2_demo_guide.md)
- [OSM and simulation methodology](docs/bengaluru_osm_geographical_twin.md)
- [Current OSM queue-model results](reports/phase2_osm_results.md)
- [Phase 2 handoff summary](docs/phase2_handoff_summary.md)
- [Phase 2 requirement-by-requirement audit](docs/phase2_audit_report.md)

All simulation demand, fleet mixes, and converted signal timing are assumptions. OSM supplies road geography, not measured traffic volumes, fleet shares, origin-destination demand, or field signal plans. The historical dataset is not used as real-time arrivals. No live traffic signals or public roads are controlled.
