# Phase 2 Runbook

This runbook is for the Bengaluru OSM-derived SUMO prototype. It predicts simulated queue length **60 seconds** ahead. The Phase 1 model predicts daily Traffic Volume and is separate. SUMO demand and vehicle behavior are assumptions, not measured Bengaluru arrivals.

## Environment and test suite

Use Linux/WSL and Python 3.12 for Metaflow. From the repository root, create a dedicated environment and install the pinned Phase 2 dependencies plus the small Phase 1 test additions:

```bash
python3.12 -m venv .venv-phase2
source .venv-phase2/bin/activate
python -m pip install -r requirements-phase2.txt -r requirements-test-phase1.txt
```

For the unit suite, from the same root:

```bash
python -m unittest discover -s tests -v
```

Latest local run: **34 unittest cases passed, 0 failed/errors** in WSL Ubuntu / Python 3.12.3. The test suite does not establish a successful GitHub Actions run; see `reports/phase2_verification_20261111.md`.

## Data and split

The current labeled input is `sumo/bengaluru_osm/datasets/osm_v2b/training_labels_incident_quarantined.csv`. It contains 357,124 rows after incident quarantine. Train/validation/test are separated by complete seeds: 7/42/2026, 99, and 123/31415. Labels match exactly +60 seconds within the same run, intersection, and lane. The current Metaflow flow delegates to the same evaluator and records local run artifacts.

If the files are DVC-managed, obtain them only through the team's reviewed DVC process. Do not copy model/data into Git. The supplied archive omitted local DVC configuration; DVC remote access remains unverified.

## Metaflow

The non-training graph check is:

```bash
python flows/bengaluru_queue_model_flow.py --metadata=local --datastore=local check
```

To execute training, first confirm the dataset is present and select a new artifact root so existing outputs are preserved:

```bash
python flows/bengaluru_queue_model_flow.py \
  --metadata=local --datastore=local \
  run \
  --dataset "$PWD/sumo/bengaluru_osm/datasets/osm_v2b/training_labels_incident_quarantined.csv" \
  --artifact-root "$PWD/reports/metaflow/bengaluru"
```

The flow/evaluator use the declared complete-seed groups and write a new timestamp/run-ID directory. Latest run `1794405200312669` reproduced the test metrics and stores the serialized model, metadata, dataset hash, and metrics as Metaflow artifacts. Inspect or export the hash-verified candidate with:

```bash
python scripts/model_registry_report.py --run-id 1794405200312669
python scripts/model_registry_report.py --run-id 1794405200312669 --export-model /tmp/queue-model-1794405200312669.joblib
```

The local Metaflow datastore is not a shared registry.

## API and local HTTP smoke test

The API expects the deployment-candidate model, its SHA-256, and a sanitized metadata file. The model is intentionally outside the Docker image. After building the image and preparing the artifact through an approved local path, run:

```powershell
docker build -t traffic-queue-api:local .
$model = (Resolve-Path .\models\bengaluru\bengaluru_queue_hurdle_v1_2026-11.joblib).Path
docker run --rm -p 8000:8000 `
  --mount "type=bind,source=$model,target=/models/bengaluru_queue_hurdle_v1_2026-11.joblib,readonly" `
  -e QUEUE_MODEL_PATH=/models/bengaluru_queue_hurdle_v1_2026-11.joblib `
  -e QUEUE_MODEL_METADATA_PATH=/app/src/api/bengaluru_deployment_metadata.json `
  -e QUEUE_MODEL_SHA256=72bc01ba9b659eeb47cd977b9bfb691e552da9f610bf637a96b05d3d36f9ea71 `
  traffic-queue-api:local
```

Endpoints are `/api/v1/health`, `/api/v1/model-info`, and `/api/v1/predict`. The current API contract uses 11 features and `queue_length_m_t_plus_60s`. A local Docker build/run and endpoint smoke check succeeded in this environment; no image was pushed.

## CI, deployment, and remaining external steps

`.github/workflows/phase2-ci.yml` contains unit tests, Python compile checks, Metaflow graph checks, Docker build, and gated deployment jobs. It triggers on `main`, `phase2-*` branch pushes, pull requests, and manual dispatch. It has not yet run on GitHub. DVC remote access and large-file availability remain unverified; do not add credentials to CI.

Render is the selected platform; `render.yaml` disables automatic deploys and pins the expected model SHA. A Render service and stable HTTPS model artifact URL still need configuration. Set `QUEUE_MODEL_URL` in Render, and `RENDER_DEPLOY_HOOK_URL` plus `RENDER_SERVICE_URL` as GitHub Actions secrets in the protected `production` environment. Then dispatch Phase 2 CI from `main` with `deploy_production=true`. No hosted prediction service is currently claimed.

## Important constraints

- The queue target is +60 seconds, not +300 seconds.
- Historical daily `Traffic Volume` is not a real-time arrival rate.
- Positive-queue errors are materially larger than all-row errors.
- Controller comparisons with teleports/collisions are quality failures; current evidence does not show predictive superiority.
- Dataset source license is unverified. OSM attribution/license is documented separately.
- No live traffic control, field validation, or real-world performance claim is made.
