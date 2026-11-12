# Phase 2 demo guide

This demo shows the queue-prediction inference service running locally in Docker. It uses simulated traffic-state inputs and predicts queue length 60 seconds ahead. It does not connect to live traffic signals or prove real-world performance.

## Start it

Open PowerShell in the project root, ensure Docker Desktop is running, and build the API image:

```powershell
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  $env:PATH = "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin;$env:PATH"
}
docker build -t traffic-queue-api:phase2-demo .
```

Start the API with the reviewed model mounted read-only. The model is not in Git; stage the Metaflow run `1794405200312669` file (SHA-256 `167b523f…0b13b`) first:

```powershell
$modelPath = ".\models\bengaluru\bengaluru_queue_hurdle_v1_2026-11.joblib"
if (-not (Test-Path $modelPath)) { throw "Stage the 167b model at $modelPath first (it is not in Git)." }
if ((Get-FileHash $modelPath -Algorithm SHA256).Hash -ne "167B523FC8C89199F6A8BF0689475272654DB96B59B8A1DA9B8A9986BFF0B13B") { throw "Wrong model file." }
$model = (Resolve-Path $modelPath).Path
docker run --rm -p 8000:8000 `
  --mount "type=bind,source=$model,target=/models/bengaluru_queue_hurdle_v1_2026-11.joblib,readonly" `
  traffic-queue-api:phase2-demo
```

Leave that terminal open. In a browser, open `http://localhost:8000/docs` to demonstrate the interactive API. Try these endpoints:

1. `GET /api/v1/health` — expect `status: ok` and `model_loaded: true`.
2. `GET /api/v1/model-info` — shows the model version, 60-second target, feature list, and SHA-256.
3. `POST /api/v1/predict` — use `reports/demo_smoke_20261111/heldout_positive_sample_request.json` for a nonzero held-out example. The captured response in `heldout_positive_sample_result.json` predicts 5.1657 m against an observed future queue of 11.0 m for that one seed-123 row. This example is illustrative, not the model's performance summary; use `reports/phase2_osm_results.md` for aggregate evaluation.

Press `Ctrl+C` in the Docker terminal to stop and remove the container.

## What to say

“This is our locally containerized inference demo. It accepts the current simulated traffic state and returns a predicted queue length 60 seconds ahead. The API checks that the selected model matches its recorded hash. The demonstration uses a synthetic example request and a local container; it is not a public deployment or live Bengaluru traffic feed.”

## Recorded output

The actual smoke-test responses are saved under `reports/demo_smoke_20261111/`. They show health, model metadata, a synthetic request, and a held-out positive-queue request/prediction captured on 2026-11-11. The held-out example predicted 5.1657 m for an observed 11.0 m queue; this single row is not a performance metric. Those captures used the earlier `72bc…` file. On 2026-11-12 the `167b` model returned the same 5.1656687762 m for that request through the API (not in a container). Aggregate results are in `reports/phase2_osm_results.md`.
