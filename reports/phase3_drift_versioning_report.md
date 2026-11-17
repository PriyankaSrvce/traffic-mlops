# Phase 3 Report: Drift, Versioning, Dashboard, Governance

Date: 2026-11-15. Production model at start: `167b523f…` (v1). All numbers below come from
files in this repository: `reports/phase3_drift/drift_report.json`,
`reports/phase3_drift/promotion_comparison.json` and `registry/model_versions.json`.

## 1. Induced drift

| Batch | How it was produced | Rows |
|---|---|---|
| Normal (control) | Original held-out test seeds 123, 31415 | 112,176 |
| Surge 600 veh/h | New SUMO runs, seeds 777 + 888, demand 11 % above the training maximum (540) | 55,556 |
| Surge 720 veh/h | New SUMO runs, seeds 777 + 888 | 63,688 |
| Sensor fault | Normal test batch with `mean_speed_mps` × 3.6 (speed reported in km/h); clearly tagged synthetic | 112,176 |

Script: `sumo/bengaluru_osm/run_drift_scenarios.py`, which reuses the project's own
generate → collect → label steps; and `sumo/bengaluru_osm/make_sensor_fault_batch.py`.

## 2. Detection and monitoring

`sumo/bengaluru_osm/drift_detection.py` loads the model only after its SHA-256 matches, scores
each batch, and applies the alert policy (`docs/GOVERNANCE.md` §5).

| Batch | Worst PSI (feature) | MAE | vs approved 0.0550 | Data | Performance | Action |
|---|---|---|---|---|---|---|
| Normal | 0.014 (queue, occupied lanes) | 0.0550 | 0 % | OK | OK | No action |
| Surge 600 | 0.123 (queue, occupied lanes) | 0.0877 | +59 % | WATCH | ALERT | Retraining recommended |
| Surge 720 | 0.168 (queue, occupied lanes) | 0.0769 | +40 % | WATCH | ALERT | Retraining recommended |
| Sensor fault | 0.765 (speed, occupied lanes) | 0.0556 | +1 % | ALERT | OK | Investigate data pipeline |

### Method finding

The original PSI used quantile bins. With 97.5 % zeros, all bins collapsed into one. Measured
with the original function, PSI was 0.000 for queue, vehicle count, halting count and speed on
**both surge batches and on the sensor-fault batch** (largest value: 0.00001), so all drift was
invisible.
`monitoring.psi` now gives the zero mass its own bin. On top of that, the detector computes PSI
on occupied lanes (`vehicle_count > 0`): on all rows the surge reached only 0.007–0.011, while on
occupied lanes it reached 0.12–0.17. Normal data stayed at 0.014, so the change does not raise
false alarms on normal data.

## 3. Retraining and versioning

1. 12 refresh runs (surge 600 and 720 × seeds 7, 42, 2026, 99, 123, 31415, matching the evaluator's
   seed split) → `aggregate_dataset.py` (incident quarantine) → `build_refresh_dataset.py`
   (merged with the unchanged v1 data; manifest of input and output hashes).
2. Metaflow `BengaluruQueueModelFlow` run 3 on the merged data (607,924 rows, 30 runs): passed all 4 quality-gate conditions. Model SHA `8da60b0e…`.
3. `scripts/model_promotion.py compare`, with production and candidate on the same rows:

| Set | Persistence | v1 167b | v2 8da6 | Check |
|---|---|---|---|---|
| Original test | 0.0694 | 0.0550 | 0.0527 | P2 no regression: PASS |
| Surge test seeds | 0.0759 | 0.0901 | 0.0601 | P3 improves: PASS |
| Unseen surge 600 | 0.0992 | 0.0877 | 0.0758 | P3 improves: PASS |
| Unseen surge 720 | 0.1011 | 0.0769 | 0.0761 | P3 improves: PASS (small, +1 %) |

Decision: **approved for promotion; awaiting human deployment approval (P4)**. v1 stays in
production and remains the recorded rollback target. The registry keeps all four versions,
including the rejected v0 and the superseded `72bc` build.

## 4. Dashboard

`GET /dashboard` on the API (FastAPI). It shows:
- live health and the served SHA from `/api/v1/model-info`;
- the pipeline stages;
- drift charts and the drift table;
- the version timeline;
- the v1-vs-v2 comparison;
- live GitHub Actions runs;
- a live prediction button;
- the governance controls.

Its data comes from `/api/v1/dashboard-data`, built by `scripts/build_dashboard_data.py` from the
JSON reports above.

## 5. Governance

`docs/GOVERNANCE.md` (framework with justification) and `docs/MODEL_CARD.md`.

## 6. Verification

- Unit tests: 44 pass. That is 34 existing plus 10 new in `tests/test_phase3_drift_and_versioning.py` (PSI on zero-inflated data, the 4 drift actions, schema alert, sensor-fault transform, promotion policy, dashboard packaging).
- Dashboard checked locally (desktop and phone width): every section renders, the live prediction returns 5.1657 m with SHA `167b…`, and GitHub runs load.
- Metaflow UI shows run 3 with all artifacts beside run 2.

## 6a. Addendum, 2026-11-16: tools named in the course circular

Added after checking the project against the course circular. Earlier sections are unchanged.

| Item | What was added | Evidence |
|---|---|---|
| Matched control batch | `normal_validation` (balanced vehicle mix, like the surge runs): worst PSI 0.053, MAE 0.0513, no action | `reports/phase3_drift/drift_report.json` |
| Evidently | DataDriftPreset + RegressionPreset per batch, on all rows and on occupied lanes. No drift on normal data; queue, vehicle-count and halting-count drift on occupied lanes under both surges (scores 0.13–0.22, threshold 0.1); speed drift under the sensor fault (1.48). On all rows the surges show no drift, as with PSI | `evidently_drift_report.py`, `reports/phase3_drift/evidently_summary.json`, `/reports/evidently/…` |
| Python logging | Structured log line per prediction, feedback record, model load/rejection and failed prediction | `src/api/app.py` |
| Prometheus / Grafana | `/metrics` endpoint; local stack with a provisioned Grafana dashboard | `monitoring/` |
| Simulated production traffic | Replay of normal → surge → sensor-fault rows with ground-truth feedback: 1,800 requests, 0 failures; live MAE 0.83 m → 1.34 m → 1.17 m; persistence 1.33 m → 1.66 m → 1.69 m (600 occupied-lane rows per phase) | `scripts/replay_production_traffic.py` |
| Retraining trigger | Decision `TRIGGER_RETRAINING` for surge_600 and surge_720; sensor fault routed to pipeline investigation. The trigger launched Metaflow (runs 4 and 5), which reproduced model `8da60b0e…` | `scripts/retraining_trigger.py`, `reports/phase3_drift/retraining_request.json` |
| PyTest | Suite runs with PyTest in CI: 60 tests pass | `pytest.ini`, CI workflow |
| DVC | Pointer files for the v1 and v2 training data and the three drift batches | `data/sumo/` |

Two cautions recorded honestly:
- Evidently's first run flagged `vehicle_composition` on normal data, because the reference was about half motorcycle-heavy and the batches all balanced. Reference and batches are now compared on the same vehicle mix.
- Evidently's dataset-level flag (50 % of columns) stays off under the surge: 3 of 8 columns drift. The policy acts on column-level results.

## 6b. Addendum, 2026-11-17: v2 redeployed

- **Approval and deployment.** v2 (`8da60b0e…`) was approved by a team member and deployed: artifact at tag `model-8da6`; `QUEUE_MODEL_SHA256` changed in `Dockerfile`, `render.yaml`, the deployment metadata and the Render service; deploy job run (CI run #25).
- **Pre-deployment test.** The built image downloaded the artifact from the published URL, passed the SHA check and matched the offline model on 300 held-out rows (max difference 3.6e-15 m). A container given the v1 SHA with the v2 file refused to start.
- **Live verification.** `/api/v1/model-info` reports `8da60b0e…`; 120 held-out rows sent to the live API match the offline model (max difference 1.1e-14 m).
- **Registry.** v2 → `production`; v1 → `archived`, rollback target. `scripts/model_promotion.py rollback` prints v1's settings.
- **Drift check after redeployment** (`reports/phase3_drift/drift_report_post_v2.json`, reference = v2 training split):

| Batch | Worst PSI | MAE v1 → v2 | MAE ÷ persistence MAE, v1 → v2 | Action with v2 |
|---|---|---|---|---|
| Normal test | 0.022 | 0.0550 → 0.0527 | 0.79 → 0.76 | No action |
| Normal, balanced mix | 0.070 | 0.0513 → 0.0512 | 0.68 → 0.68 | No action |
| Surge 600 | 0.112 | 0.0877 → 0.0758 | 0.88 → 0.76 | Retraining recommended (+36 % vs approved 0.0558) |
| Surge 720 | 0.145 | 0.0769 → 0.0761 | 0.76 → 0.75 | Retraining recommended (+36 %) |
| Sensor fault | 0.763 | 0.0556 → 0.0539 | 0.80 → 0.78 | Investigate data pipeline |

  v2 has the same advantage over persistence in surge as in normal traffic, so the retraining restored the model's skill. The absolute-error rule still fires under surge because surge traffic is harder for every predictor. The threshold was not changed after seeing this; the rule is recorded for review in `docs/GOVERNANCE.md` §5.3.



- Drift batches are simulated scenarios and one synthetic fault, not live traffic.
- Monitoring runs as a batch job, not as a live stream.
- (Superseded on 2026-11-17, see §6b.) At the time of the original report v2 was not deployed.

## Reproduce

```bash
python sumo/bengaluru_osm/run_drift_scenarios.py --output-root runs/drift_v1
python sumo/bengaluru_osm/make_sensor_fault_batch.py splits/test.csv runs/drift_v1/sensor_fault_kmh_test.csv
python sumo/bengaluru_osm/drift_detection.py --reference splits/train.csv \
  --batch normal_test=splits/test.csv --batch surge_600=runs/drift_v1/surge_600_combined.csv \
  --batch surge_720=runs/drift_v1/surge_720_combined.csv --batch sensor_fault_kmh=runs/drift_v1/sensor_fault_kmh_test.csv
python sumo/bengaluru_osm/run_drift_scenarios.py --seeds 7,42,2026,99,123,31415 --batch-id retrain_v2 --output-root runs/retrain_v2
python sumo/bengaluru_osm/aggregate_dataset.py --roots runs/retrain_v2 --output datasets/refresh_v2
python sumo/bengaluru_osm/build_refresh_dataset.py --base training_labels_incident_quarantined.csv \
  --refresh datasets/refresh_v2/training_labels_incident_quarantined.csv --output datasets/training_labels_v2.csv
python flows/bengaluru_queue_model_flow.py run --dataset datasets/training_labels_v2.csv
python scripts/model_promotion.py compare --production MODEL_V1:SHA --candidate MODEL_V2:SHA --gate-passed \
  --set original_test=splits/test.csv --drift-set surge_600_unseen=runs/drift_v1/surge_600_combined.csv ...
python scripts/build_dashboard_data.py --tests 44
```

(The surge `*_combined.csv` files are the two seeds' `labeled.csv` concatenated.)
