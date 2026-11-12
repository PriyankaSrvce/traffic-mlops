# Phase 2 Verification — 2026-11-12

Independent re-verification of `main` @ `d85890058a13` using the team handover package
(`phase2-antigravity-handover-20261112.zip`) and its Metaflow evidence archive. It also reconciles
the audit reports in PR #5. This record separates **verified** results from **not verified**
and **blocked** items. No data, model binary, credential or DVC cache is added to Git.

## Environment

- WSL Ubuntu 24.04.4, Python 3.12.3, isolated venv created with `uv` from `requirements-phase2.txt` + `requirements-test-phase1.txt`
  (numpy 2.2.6, pandas 2.3.3, scikit-learn 1.7.2, joblib 1.6.0, metaflow 2.19.41, fastapi 0.159.1, pydantic 2.14.1, uvicorn 0.54.0).
- No SUMO, no DVC, no working Docker engine on this machine.

## Verified

### Inputs (SHA-256 / row checks, stdlib only)

| Item | Result |
|---|---|
| `training_labels_incident_quarantined.csv` | SHA-256 `4e8213df71d3ed2df8bb2995ec195e1610f4398ad37f0e049a4399d9f93a5ffb`; 357,124 rows × 22 columns; 18 runs; no run spans two seeds |
| Splits (`train/validation/test.csv`) | SHA-256 and run-ID sets equal `splits/manifest.json`; 185,896 / 59,052 / 112,176 rows; seeds 7/42/2026, 99, 123/31415; no run overlap |
| Labels | All 357,124 targets equal `queue_length_m` 60 s later on the same run/intersection/lane (342,988 checked within the file, 14,136 against `observations_all.csv`); 0 mismatches |
| Test zero share | 109,423 / 112,176 = 97.5458 %; 2,753 positive-target rows |
| DVC payloads in the handover package | md5 of all 5 pointer payloads (`bengaluru_osm_sim.net.xml`, etc.) equal their `.dvc` files |

### Tests and Metaflow

```bash
python -m unittest discover -s tests -v                       # Ran 34 tests ... OK
python flows/queue_model_flow.py --metadata=local --datastore=local check            # OK
python flows/bengaluru_queue_model_flow.py --metadata=local --datastore=local check  # OK
python flows/bengaluru_queue_model_flow.py --metadata=local --datastore=local run \
  --dataset <handover>/sumo/bengaluru_osm/datasets/osm_v2b/training_labels_incident_quarantined.csv \
  --artifact-root <scratch>/artifacts
```

Run `1794473115185929`: all 4 steps succeeded. Rows 357,124, dataset SHA `4e8213df…5ffb`, threshold 0.99, all gates passed.
**Model SHA-256 `167b523fc8c89199f6a8bf0689475272654db96b59b8a1da9b8a9986bff0b13b`**: byte-identical to runs
`1794370252312711` and `1794405200312669`. In the evidence archive, the `model_blob` artifact of run `1794405200312669` contains exactly these bytes.

### Model identity

| File | SHA-256 | Notes |
|---|---|---|
| Metaflow model (promoted) | `167b523f…0b13b` | reproduced bit-for-bit in the pinned WSL environment |
| Earlier deployment candidate | `72bc01ba…ea71` | produced on Windows by a former DVC stage; differs in serialization bytes only |

Both were loaded only after their SHA-256 was checked. Their feature order matches training (11 features). Threshold 0.99, 120 + 120 trees.
Predictions differ by at most 7.1e-15 m on all 112,176 test rows.

### Held-out metrics (identical 112,176 rows; persistence = current `queue_length_m`)

| Subset | n | Model MAE / RMSE / R² | Persistence MAE / RMSE / R² |
|---|---:|---|---|
| All rows | 112,176 | 0.05500 / 0.51355 / 0.88357 | 0.06935 / 0.65129 / 0.81274 |
| Future queue > 0 | 2,753 | 2.19955 / 3.23686 / 0.66734 | **1.90200** / 3.43766 / 0.62479 |
| Current or future > 0 | 3,357 | **1.8321** / 2.9620 | 2.3175 / 3.7648 |
| Future queue = 0 | 109,423 | **0.00105** / 0.0823 | 0.02325 / 0.3708 |

On positive-future rows the model's MAE is 15.6 % worse than persistence, while its RMSE is 5.8 % better.
Claims of a 3.3281 m persistence MAE or a "33.9 %" positive-subset improvement (PR #5 audit files) are **incorrect**.

Isolation: preprocessing, classifier and regressor are fit on train seeds only. The threshold is chosen on validation seed 99.
The test set feeds two pass/fail acceptance gates only.

### API (uvicorn, 127.0.0.1, `167b` via `QUEUE_MODEL_PATH` / `QUEUE_MODEL_METADATA_PATH` / `QUEUE_MODEL_SHA256`)

- `/health`, `/api/v1/health`: 200 `{"status":"ok","model_loaded":true,"validation_status":"passed"}`.
- `/model-info`: 200, SHA `167b…`, target `queue_length_m_t_plus_60s`, 60 s, metres.
- `/api/v1/predict`: 300 real held-out rows (200 positive-target) all returned 200. Max difference from the recorded Metaflow predictions was 7.1e-15 m.
  `reports/demo_smoke_20261111/heldout_positive_sample_request.json` → **5.1656687762 m** (same value the `72bc` container returned on 2026-11-11).
- Extra field or negative value → 422.
- Configured hash `72bc…` with the `167b` file → **startup refused** (`ValueError`, exit 1; also refused by `docker_entrypoint.py`). A missing model file → 503 on all endpoints.
  An `http://` model URL is rejected by the entrypoint.

### GitHub Actions (public API)

| Run | Event / ref / sha | Result |
|---|---|---|
| 43036696130 | push / phase2-completion-20261111 / a85972c | checks success; deploy skipped |
| 43039410684 | push / main / d858900 | checks success; deploy skipped |
| 43060494475 | workflow_dispatch / main / d858900 | checks success; **deploy success** |
| 43179599071 | pull_request / docs/phase2-audit-handover / 9e764ad | success |

The deploy job fails when its secrets are missing. Its success therefore means the deploy hook was accepted and `/health` returned 200.
The job logs need a GitHub login and were not read.

## Not verified

- **Hosted inference:** the Render service URL is not recorded. No hosted `/model-info` or `/predict` response exists. The CI deploy used the earlier `72bc` pin.
- **Docker container with `167b`:** the local Docker Desktop engine failed to start (installation registry keys missing), so no image was built on 2026-11-12. The previous container smoke test (2026-11-11) used `72bc`.
- **SUMO controller experiments:** not re-run (SUMO not installed). Recorded summaries: fixed-time had the lowest mean travel time in every clean batch (low: 504.08 / 507.61 / 507.27 s; medium-300: 531.30 / 536.10 / 536.74 s for fixed / adaptive / predictive). Other medium/high batches have teleports or collisions.
- **DVC remote:** not contacted.

## Open items

1. Before the next Render deploy, host the exact `167b` file at `QUEUE_MODEL_URL`; the blueprint and image now pin `167b`.
2. Build and run the container once Docker works, then record hosted `/model-info` and `/predict` responses.
3. Confirm that `osm_v1`-labelled training runs (low/medium seeds 7, 42, 99) share the network and queue definition of the `osm_v2` runs.
4. The selected threshold (0.99) is at the top of its search grid; report this as a limitation.
5. Correct the PR #5 audit files (wrong hashes, model type, persistence figures, hash-mismatch behaviour); see the reviewer notes supplied with this record.
6. Monitoring is offline batch only (PSI, metrics, feedback ledger); there is no live telemetry.
