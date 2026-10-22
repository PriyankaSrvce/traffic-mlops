# Future SUMO Data Specification (Proposal)

**Status:** Future proposal only. SUMO data collection, queue-label generation, and queue prediction are not implemented. The final network, detector or TraCI collection method, queue definition, and sampling interval must be confirmed with Member 3 before implementation.

## Proposed observation schema

Store one observation per simulation run, timestamp, intersection, and approach/lane. If the chosen simulator network has no lane-level measurement, document the approach-level aggregation instead of inventing lane identifiers.

| Field | Meaning |
|---|---|
| `run_id` | Unique simulation execution/seed identifier; required to prevent joining observations across runs. |
| `simulation_time_s` | Elapsed SUMO simulation time in seconds. A sampling cadence is not yet selected. |
| `intersection_id` | Stable identifier from the selected network; topology is not yet selected. |
| `approach_id` | Inbound approach identifier at the intersection. |
| `lane_id` | Lane identifier when measured per lane; null only when a documented approach-level aggregate is used. |
| `queue_length_m` | Current queue length in metres at `simulation_time_s`, under the proposed definition below. |
| `queue_definition_id` | Version/configuration for the queue rule, including speed threshold and measured lane/link segment. |
| `vehicle_count`, `flow_veh_per_hour`, `mean_speed_mps`, `occupancy_or_density` | Candidate current traffic-state measurements, all measured at or before this observation time. Exact availability and units for occupancy/density remain to be confirmed. |
| `signal_phase_id`, `signal_state`, `phase_elapsed_s` | Candidate current signal state at the intersection and observation time. Availability and phase semantics depend on Member 3's implementation. |
| `queue_length_m_t_plus_300s` | Supervised target: queue length in metres for the same run and approach/lane at exactly `simulation_time_s + 300`. |

### Proposed queue measurement

Proposed measurement location: on the measured inbound lane, from its stop line upstream to the rear bumper of the last vehicle in a contiguous stopped queue; include the gaps between queued vehicles. Define a vehicle as queued when its speed is at or below a proposed threshold of **0.1 m/s**. Record zero when no vehicle meets that rule. If the queue reaches beyond the available upstream lane/link segment, flag the measurement as truncated rather than treating the segment length as the true queue length.

This is a concrete proposal, not a confirmed project definition. Member 3 must confirm the speed threshold, whether gaps are included, available measurement segment, truncation handling, and whether measurements are per lane or aggregated per approach after the final network is known.

## Future label creation and leakage controls

For each current observation at time `t`, find the observation with the exact same `run_id`, `intersection_id`, `approach_id`, and `lane_id` at `t + 300` seconds. Copy its `queue_length_m` into `queue_length_m_t_plus_300s`. Do not join across runs, approaches, lanes, or approximate timestamps. If the exact future observation is unavailable, keep the row for analysis with a missing target and exclude it from supervised training; do not interpolate or carry a queue value forward.

For future model evaluation, prefer assigning complete independent simulation runs/scenarios to separate train, validation, and test partitions when enough runs exist, keeping each run/scenario in only one partition. If there are too few independent runs, use chronological blocks and purge observations whose `t + 300` label would cross a partition boundary, including the 300-second horizon before the boundary. Exclude observations whose future measurement is unavailable or falls outside its own partition. Fit preprocessing only on training data. Apply any additional purge needed once the sampling cadence is selected.

Keep these simulated observations and labels in a separate dataset location/version from `data/raw/bangalore_traffic.csv` and its daily `Traffic Volume` target. Do not combine the datasets as if their measurements or targets were interchangeable.

## Decisions to confirm with Member 3

- Final SUMO network, intersection/approach/lane identifiers, and observation granularity.
- Queue measurement mechanism, speed threshold, gap convention, upstream segment, and truncation behavior.
- Simulation sampling interval and whether every required exact `t + 300` observation will be recorded.
- Which current traffic and signal-state fields the selected SUMO interface can provide consistently.
- Run/scenario metadata and separate storage location for simulation outputs.
