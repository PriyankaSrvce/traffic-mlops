# Model Card: Bengaluru 60-second Queue Predictor

| | v1 (production) | v2 (approved, awaiting deployment) |
|---|---|---|
| SHA-256 | `167b523fc8c89199f6a8bf0689475272654db96b59b8a1da9b8a9986bff0b13b` | `8da60b0e70a0e38c3e4c5d82eefd47fd170949997e62b9bbf3f573ebb03c0804` |
| Metaflow run | `BengaluruQueueModelFlow/1794405200312669` (also reproduced as run 2) | `BengaluruQueueModelFlow/3` |
| Dataset SHA-256 | `4e8213df…5ffb` (357,124 rows, 18 runs) | `177130ea…93c4` (607,924 rows, 30 runs = v1 data + 12 surge runs) |
| Registry stage | production (live on Render) | approved (passed P1–P3; P4 human deployment pending) |

## Intended use

- **Predicts:** queue length (metres) on one lane, 60 seconds ahead, from the lane's current
  state (queue, vehicle counts, speed, signal phase and timing, location, vehicle mix).
- **Intended for:** research and teaching on a SUMO digital twin of an OSM-derived Bengaluru
  corridor (35 signalised junctions). Input to adaptive-signal experiments.
- **Not intended for:** controlling real traffic signals, or for forecasts on roads outside the
  simulated corridor, without field validation.

## Model

Hurdle model:
1. a Random Forest classifier answers "will there be a queue in 60 s?" (threshold 0.99);
2. a Random Forest regressor answers "how long?", trained on rows with a queue.

**Why a hurdle model:** 97.5 % of observations have no queue. A single regressor (v0) spent its
capacity on the zeros and failed the quality gate.

## Training data

- SUMO 1.28 simulations on `bengaluru_osm_sim.net.xml`, 900 s per run, observations every 10 s.
- Demand: low 180 / medium 420 / high 540 veh/h (v1); v2 adds surge 600 and 720 veh/h. All
  demand levels and vehicle mixes are **assumptions**, not measured counts.
- Observations within 60 s of a collision or teleport are removed (incident quarantine).
- Split by **whole simulation seed**: train 7, 42, 2026; validation 99; test 123, 31415.

## Evaluation

Baseline: **persistence** (the queue in 60 s equals the queue now).

| Evaluation set (same rows for both models) | Rows | Persistence MAE | v1 MAE | v2 MAE |
|---|---|---|---|---|
| Original test (normal demand) | 112,176 | 0.0694 | 0.0550 | 0.0527 |
| Surge test seeds 123, 31415 | 80,256 | 0.0759 | 0.0901 | 0.0601 |
| Unseen surge 600 veh/h (seeds 777, 888) | 55,556 | 0.0992 | 0.0877 | 0.0758 |
| Unseen surge 720 veh/h (seeds 777, 888) | 63,688 | 0.1011 | 0.0769 | 0.0761 |

Source: `reports/phase3_drift/promotion_comparison.json`.

Quality gate (Metaflow `acceptance` step): on both validation and test, MAE must be ≥ 5 % lower than persistence and RMSE no higher. v1 and v2 both passed.

### Known weaknesses (disclosed)

- **Positive-queue rows:** on v1's test rows where a queue will exist (2,753 rows),
  persistence has lower MAE (1.90 m vs 2.20 m). The model's overall advantage comes mostly from
  correctly predicting that queues clear.
- **v1 under surge:** on surge test seeds v1 was *worse* than persistence (0.0901 vs 0.0759).
  This is the main reason v2 was trained.
- **Severe surge (720 veh/h, unseen seeds):** v2 improves only slightly (0.0769 → 0.0761).
- Results come from simulation. No field-observed queue labels exist.

## Monitoring

Batch drift checks (`sumo/bengaluru_osm/drift_detection.py`): PSI on all rows and on occupied
lanes, MAE versus the approved test MAE, the persistence margin, and unseen categories. Policy
and Phase 3 results: `docs/GOVERNANCE.md` §5 and the `/dashboard` page.

## Ethical and safety considerations

- Errors are reported per intersection, demand level and vehicle mix, so no corridor segment is quietly served worse.
- The project makes **no claim** that predictive signal control beats fixed-time control. That was not supported by the verified experiments.
- Any real deployment would need field validation, a fallback controller, and the model in an advisory role only.
