# Phase 2 Handoff Summary

## What is implemented

- An OSM-derived Bengaluru corridor simulation with explicitly assumed demand, vehicle mix, and converted signal plans.
- A SUMO queue target exactly 60 seconds ahead, a seed-separated Metaflow training/evaluation flow, persistence comparison, and local artifact/hash records.
- Fixed-time, adaptive, and predictive signal policies; paired experiment evaluation; a FastAPI inference service; a Docker image definition; a manual Render deployment blueprint; and a GitHub Actions workflow.
- Unit tests for Phase 1 features/training and Phase 2 API, model catalog, scenario, monitoring, and route-generation behavior.

## Evidence already recorded

The existing `reports/final_results_report.md` is preserved from the repository and contains older composite/grid experiment claims. Use `reports/phase2_osm_results.md` for the current OSM model results; do not mix their metrics or horizons.

- The OSM queue-model report at `reports/phase2_osm_results.md` records test MAE 0.055003 m and RMSE 0.513549 m versus persistence MAE 0.069353 m and RMSE 0.651288 m on the same 112,176 rows. Positive-queue subset: 2,753 rows, model MAE 2.199547 m and RMSE 3.236860 m. This is synthetic SUMO evidence, not field validation.
- Two fresh local Metaflow runs are documented as reproducing those metrics. Local run tracking is not a shared hosted registry.
- The local suite passed 34 unittest cases in WSL Python 3.12.3. The local Docker/API smoke checks passed. GitHub Actions run `43036696130` passed on the feature branch (deploy skipped). On `main` (`d858900`), push run `43039410684` passed (deploy skipped) and manual run `43060494475` passed checks and the gated deploy job. Recomputation on 2026-11-12 found persistence has the lower MAE on the 2,753 positive-future rows (1.902 vs 2.200 m); see `reports/phase2_verification_20261112.md`.
- The checked-in `reports/demo_smoke_20261111/` files are captured local responses; the included SUMO screenshot is an actual GUI replay, not a generated mock-up.
- Controller results do not establish that predictive control is best. The clean medium-300 batch reported mean travel time 531.30 s fixed, 536.10 s adaptive, and 536.74 s predictive.

## Important limits and remaining blockers

> Latest local test, fresh Metaflow registry, API, Docker, and DVC evidence is in `reports/phase2_verification_20261111.md`.

1. **DVC:** `dvc.yaml` and `dvc.lock` remain unchanged. Local `dvc status` reports data/model/network outputs missing from the handover checkout/cache. Remote state was not checked. Private authentication and pipeline/lock reconciliation remain needed before shared reproduction.
2. **CI:** workflow now runs for `main`, `phase2-*` branch pushes, pull requests, and manual dispatch. Feature-branch run `43036696130` passed tests, graph checks, and image build. Production deployment is a separate manual step; it ran once (run `43060494475` on `main`) and its health poll succeeded.
3. **Hosted deployment:** Render is selected; its blueprint disables automatic deploys. CI run `43060494475` triggered the deploy hook and saw `/health` 200, configured with the earlier `72bc…` model. The service URL is not recorded in the repo, and hosted `/model-info` and `/predict` are not verified. After the promotion to `167b`, the file at `QUEUE_MODEL_URL` must be replaced before the next deploy.
4. **Model registry:** the fresh Metaflow run stores a hash-verified model artifact and record; the local registry/export check passed. There is no shared Metaflow metadata/datastore service configured.
5. **Monitoring:** PSI and feedback utilities are offline; production telemetry, alerts, and retraining are not running.
6. **Generalization:** demand and fleet proportions are assumptions; the network is not field calibrated. Some controller runs have quality failures, and no real-world improvement is claimed.

## Target distinction

Phase 1 predicts same-day daily `Traffic Volume` from the historical dataset. Phase 2 predicts simulated queue length 60 seconds ahead. The Phase 1 target is not a queue target, and its unit remains unspecified. The historical dataset license remains **unverified**.

## Local verification commands

From the repository root, the recorded local checks are:

```powershell
python -m unittest discover -s tests -v
python flows/queue_model_flow.py --metadata=local --datastore=local check
python flows/bengaluru_queue_model_flow.py --metadata=local --datastore=local check
```

The workflow also builds the Docker image. The local test/flow/Docker evidence is documented in `docs/phase2_audit_report.md`; it must not be presented as a GitHub Actions run or public deployment.
