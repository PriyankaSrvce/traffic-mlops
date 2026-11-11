# Implemented Phase 2 SUMO Data Specification

**Status:** Implemented in the current Phase 2 prototype. The code collects timestamped Bengaluru OSM-corridor SUMO observations and labels same-run queue length exactly 60 seconds ahead. This simulated target is separate from the Phase 1 historical daily `Traffic Volume` target.

## Observation and label fields

The collector writes one row for each sampled lane observation. Its exact field list is defined in `sumo/bengaluru_osm/collect_observations.py`.

| Field | Meaning / unit |
|---|---|
| `run_id`, `seed`, `scenario` | Simulation execution ID, reproducibility seed, and low/medium/high demand scenario. |
| `time_s` | Elapsed SUMO simulation time in seconds. Collector default is every 10 simulation steps; the sampling step can be configured. |
| `intersection_id`, `approach_id`, `lane_id` | Stable IDs for the signalized intersection, incoming approach, and measured lane. |
| `queue_length_m` | Physical contiguous stopped queue in metres, measured on the lane. Start with the downstream-most stopped vehicle, include upstream stopped vehicles while bumper gap is at most 2.5 m, and measure from the leading front to the last rear bumper (vehicle bodies and gaps included). A stopped vehicle has speed at or below 0.1 m/s. |
| `queue_vehicle_count`, `halting_vehicle_count` | Counts of vehicles in the contiguous queue and of all stopped vehicles on the lane, respectively. |
| `queue_proxy_5m` | Legacy estimate using 5 metres per stopped vehicle. It is not the physical queue measurement or the model target. |
| `vehicle_count`, `mean_speed_mps`, `waiting_time_s`, `occupancy_pct` | Current lane traffic state: count, mean speed in metres/second, waiting time in seconds, and SUMO occupancy percentage. |
| `vehicle_type_mix`, `vehicle_composition` | Vehicle-type and composition descriptors for the simulation. The fleet profile is assumed, not measured Bengaluru fleet data. |
| `signal_phase_id`, `signal_state`, `phase_elapsed_s` | Current signal phase identity/state and elapsed phase time in seconds. |
| `queue_length_m_t_plus_60s` | Label added by `label_observations.py`: queue length in metres exactly 60 seconds later for the same run, intersection, and lane. |

The trained Bengaluru model uses 11 current-state features: `queue_length_m`, `vehicle_count`, `halting_vehicle_count`, `mean_speed_mps`, `phase_elapsed_s`, `intersection_id`, `approach_id`, `lane_id`, `signal_phase_id`, `signal_state`, and `vehicle_composition`. The target and feature contract is also recorded in `sumo/bengaluru_osm/evaluate_hurdle.py` and the API metadata.

## Label and split rules

The labeler joins by `run_id`, `intersection_id`, and `lane_id` at the exact future timestamp `time_s + 60`. It rejects duplicate observation keys. Rows without that exact future observation are omitted from the labeled output; it does not interpolate or carry labels across runs.

The evaluated model partitions complete simulation seeds: training 7/42/2026, validation 99, and held-out test 123/31415. Runs do not cross partitions, preprocessing is fitted on training data, and the decision threshold is selected on validation. The held-out metrics are in `reports/phase2_osm_results.md`.

## Limits

This is an OSM-derived, synthetic SUMO corridor, not a field-calibrated Bengaluru-wide traffic system. Demand rates, vehicle mix, and signal plans are assumptions. The queue definition and units describe simulated measurements; they are not field ground truth. The historical dataset license remains **unverified**, and the daily historical data is not treated as SUMO arrivals.