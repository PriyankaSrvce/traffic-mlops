# Phase 2 Queue-Prediction Evaluation

**Status:** The Phase 2 model and held-out evaluation are implemented for a simulated queue target 60 seconds ahead. This is separate from the Phase 1 same-day daily `Traffic Volume` model and from older archived 300-second experiments.

## Target and data partitions

At time `t`, predict `queue_length_m_t_plus_60s` for the same `run_id`, intersection, and lane at exactly `t + 60` seconds. The measured physical queue is in metres and follows the contiguous stopped-vehicle rule in `docs/sumo_data_specification.md`. Rows without the exact future observation are excluded by the labeler.

The current evaluation assigns complete simulation seeds to partitions: train 7/42/2026 (185,896 rows), validation 99 (59,052 rows), and test 123/31415 (112,176 rows). No run crosses partitions. Preprocessing is fitted on training data only; the model-selection threshold is selected on validation data. The held-out test is reserved for final measurement and predeclared quality checks, not future tuning.

## Baseline, metrics, and measured results

The persistence baseline predicts the current observed queue as the queue 60 seconds later. Model and persistence scores use the same 112,176 held-out observations.

| Metric | Hurdle model | Persistence baseline |
|---|---:|---:|
| MAE | 0.055003 m | 0.069353 m |
| RMSE | 0.513549 m | 0.651288 m |
| R² | 0.883569 | 0.812737 |

The target is zero for many test rows. On the 2,753 held-out rows with a positive future queue, the model MAE is 2.199547 m and RMSE is 3.236860 m. Report both overall and positive-target results. These are synthetic simulation metrics, not accuracy measurements on real traffic.

## Evaluate the downstream controller separately

Queue prediction metrics do not prove that predictive signals improve traffic outcomes. Fixed-time, adaptive, and predictive policies were evaluated separately under matched simulation conditions. Existing results do not show that predictive control is best; consult `reports/phase2_osm_results.md` and `docs/phase2_perimeter_experiment_report.md` for their separate experiments and limitations.

## Remaining evaluation improvements

Increase independent runs and scenario diversity, then compare errors by intersection, approach, and traffic condition when sample counts support it. Keep all future labels within their own runs and partitions; if chronological splits are ever used, purge observations whose 60-second labels cross the partition boundary. Do not combine simulated queue labels with the historical daily traffic-volume dataset.