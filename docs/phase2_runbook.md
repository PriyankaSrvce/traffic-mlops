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

On `main` the labeled CSV, split files and model binaries are **not tracked by DVC** (`dvc.yaml` holds only Phase 1 stages; the `.dvc` pointers cover the OSM/network files and the Phase 1 CSV). Obtain the CSV from the team's verified handover package and check its SHA-256 is `4e8213df71d3ed2df8bb2995ec195e1610f4398ad37f0e049a4399d9f93a5ffb` before training. Do not copy model or data into Git. DVC remote access remains unverified; configure credentials only privately (for example in `.dvc/config.local`, which is gitignored).

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

The API expects the Metaflow run `1794405200312669` model (SHA-256 `167b523fc8c89199f6a8bf0689475272654db96b59b8a1da9b8a9986bff0b13b`) and the sanitized metadata baked into the image. The model is gitignored and intentionally outside the Docker image. Export it with the registry command above, or stage it from the verified handover package, then run:

```powershell
docker build -t traffic-queue-api:local .
$modelPath = ".\models\bengaluru\bengaluru_queue_hurdle_v1_2026-11.joblib"
if (-not (Test-Path $modelPath)) { throw "Stage the 167b model at $modelPath first (it is not in Git)." }
if ((Get-FileHash $modelPath -Algorithm SHA256).Hash -ne "167B523FC8C89199F6A8BF0689475272654DB96B59B8A1DA9B8A9986BFF0B13B") { throw "Wrong model file." }
$model = (Resolve-Path $modelPath).Path
docker run --rm -p 8000:8000 `
  --mount "type=bind,source=$model,target=/models/bengaluru_queue_hurdle_v1_2026-11.joblib,readonly" `
  traffic-queue-api:local
```

Without Docker, the same checks can be run from WSL with the pinned venv:

```bash
QUEUE_MODEL_PATH=<path>/registered-model.joblib \
QUEUE_MODEL_METADATA_PATH=src/api/bengaluru_deployment_metadata.json \
QUEUE_MODEL_SHA256=167b523fc8c89199f6a8bf0689475272654db96b59b8a1da9b8a9986bff0b13b \
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

Endpoints are `/api/v1/health`, `/api/v1/model-info`, and `/api/v1/predict`. The current API contract uses 11 features and `queue_length_m_t_plus_60s`. A wrong configured hash stops startup; a missing model file gives HTTP 503. A local Docker build/run and endpoint smoke check succeeded on 2026-11-11 with the earlier `72bc…` file. On 2026-11-12 the `167b` model was verified through uvicorn and the image entrypoint, but not in a container (the local Docker engine was unavailable). No image was pushed.

## CI, deployment, and remaining external steps

`.github/workflows/phase2-ci.yml` contains unit tests, Python compile checks, Metaflow graph checks, Docker build, and gated deployment jobs. It triggers on `main`, `phase2-*` branch pushes, pull requests, and manual dispatch. GitHub run `43036696130` passed on the feature branch (deploy skipped). On `main`, push run `43039410684` passed (deploy skipped), and manual run `43060494475` passed checks and the gated deploy job. DVC remote access and large-file availability remain unverified; do not add credentials to CI.

Render is the selected platform; `render.yaml` disables automatic deploys and pins the expected model SHA, now `167b…`. Run `43060494475` shows that the deploy-hook and service-URL secrets were configured and that `/health` returned 200, under the earlier `72bc…` pin. Before the next deploy, replace the file at Render's `QUEUE_MODEL_URL` with the exact `167b` artifact; otherwise startup is refused by design. Then dispatch Phase 2 CI from `main` with `deploy_production=true`, and record a hosted `/api/v1/model-info` and `/api/v1/predict` response. Hosted inference has not been verified.

## Important constraints

- The queue target is +60 seconds, not +300 seconds.
- Historical daily `Traffic Volume` is not a real-time arrival rate.
- Positive-queue errors are materially larger than all-row errors.
- Controller comparisons with teleports/collisions are quality failures; current evidence does not show predictive superiority.
- Dataset source license is unverified. OSM attribution/license is documented separately.
- No live traffic control, field validation, or real-world performance claim is made.
