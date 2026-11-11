# Bengaluru OSM SUMO Experiment

This folder contains an OSM-derived Bengaluru corridor, SUMO scenarios, queue collection/labeling, model evaluation, and fixed/adaptive/predictive controller code. OSM contributes road geography. Demand rates, routes, vehicle mixes, and signal timing are synthetic or assumed; the corridor is not field-calibrated.

## Current model contract

- Target: `queue_length_m_t_plus_60s` (simulated lane queue 60 seconds ahead).
- Queue measurement: contiguous downstream stopped vehicles, speed <=0.1 m/s, adjacent bumper gap <=2.5 m; length includes vehicle bodies and gaps.
- Features: 11 ordered inputs, declared by the model/API contract; includes vehicle composition.
- Partitions: complete seeds, train 7/42/2026; validation 99; held-out test 123/31415.
- Test: 112,176 rows; MAE 0.055003 m, RMSE 0.513549 m, R² 0.883569. Persistence on the same rows: 0.069353 m, 0.651288 m, 0.812737. Positive future queues: n=2,753; MAE 2.199547 m, RMSE 3.236860 m.
- Result source: `datasets/osm_v2b/hurdle_evaluation/report.json` and the saved Metaflow run record under `reports/metaflow/bengaluru/`.

These are simulated-domain metrics, not field accuracy. The separate Phase 1 model predicts same-day daily Traffic Volume. Its units are unspecified and the source dataset license is **unverified**.

The OSM scenario generator supports five vehicle classes (two-wheeler, car, auto-rickshaw, bus, truck), two assumed composition profiles, and seeded random departures across the 900-second generation interval. The labeled dataset records the assumed profile and lane-level type counts when present; the model's 11-feature contract uses the profile category, not a separate vector of per-type lane counts. Fleet shares are assumptions. This implements departure-time spread, not a separate per-vehicle reaction/startup delay.

## Reproduction

Use Linux/WSL with Python 3.12, dependencies from `requirements-phase2.txt`, and SUMO for collection/simulation. The model evaluator can be invoked directly:

```bash
python sumo/bengaluru_osm/evaluate_hurdle.py \
  --data sumo/bengaluru_osm/datasets/osm_v2b/training_labels_incident_quarantined.csv \
  --output-dir /tmp/bengaluru-evaluation \
  --model-dir /tmp/bengaluru-model
```

That command trains and writes outputs; use fresh output directories. The Metaflow flow checks are:

```bash
python flows/bengaluru_queue_model_flow.py --metadata=local --datastore=local check
```

The flow's training step writes versioned artifacts under its selected artifact root. A fresh run completed successfully on 2026-11-11 as Metaflow run `1794391865386585`, reproducing the recorded held-out metrics. Its report/model/log are kept in a separate sibling folder listed in `docs/phase2_audit_report.md`; the archive's existing Metaflow history was not overwritten. Consult `docs/phase2_runbook.md` before collecting simulations or training.

## Scenario and controller results

`controller_eval_v1` contains paired low/medium/high policy experiments with variable quality. Low runs are clean; some medium/high runs have teleports/collisions and must not be treated as clean comparisons. `controller_eval_medium_300_v1` contains nine clean runs but predictive policy was not better than fixed-time by mean travel time. Detailed summaries and caveats are in `reports/final_results_report.md`.

## Artifact and DVC handling

Large OSM networks, datasets, and model files should be obtained through the approved artifact/DVC process. The handover checkout's local `dvc status` reports the raw/processed Phase 1 files, `model.pkl`, and OSM/network outputs missing from its cache. No remote was contacted, so remote availability is unknown. Preserve pointer files and reconcile the pipeline/lock before relying on DVC reproduction; see `reports/phase2_verification_20261111.md`.
