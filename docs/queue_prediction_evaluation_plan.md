# Future Queue-Prediction Evaluation Plan (Proposal)

**Status:** Planning only. SUMO data collection, queue-length prediction, adaptive signal control, route rerouting, and deployment have not been implemented or evaluated.

## Prediction target

Use the proposed SUMO schema in `docs/sumo_data_specification.md`. At each observation time `t`, predict the same run, intersection, approach, and lane's queue length at exactly `t + 300` seconds. The provisional queue definition and metre unit must be confirmed with Member 3 after the network and measurement method are known. Do not treat the historical daily `Traffic Volume` target as a queue label or combine it with simulated observations.

## Data splits and leakage controls

- Prefer assigning complete independent simulation runs/scenarios to separate train, validation, and test partitions when enough runs exist, keeping each run/scenario in only one partition.
- If there are too few independent runs, divide observations into chronological blocks. Purge observations whose future label at `t + 300 seconds` would cross a partition boundary, including the 300-second horizon before that boundary. Exclude rows with unavailable future observations; never join targets across runs, intersections, approaches, lanes, or partitions.
- Select features and tune models using training and validation data only. Fit preprocessing only on training data. Use the test partition once for final comparison after choices are fixed.
- Keep current-state inputs restricted to information available at time `t`; the future queue measurement is a label only.

## Models and metrics

Start with a **persistence baseline**: predict the queue at `t + 300` to equal the observed queue at `t`. Compare it with a training-mean baseline and candidate regression models (for example, linear regression and tree-based models). Choose/tune candidates on validation data, then report held-out test performance.

Report MAE and RMSE in **metres**, conditional on Member 3 confirming a queue-length definition measured in metres. If the confirmed measure uses another unit, document the unit and use it consistently instead. Report sample counts alongside scores.

Report overall metrics and, when sample counts support meaningful comparisons, metrics by intersection, approach/lane, and predefined traffic conditions (such as low, moderate, and high demand). Define condition thresholds using training data only; avoid interpreting small groups as reliable comparisons.

## Separate prediction from traffic-management evaluation

First assess prediction accuracy independently using held-out queue labels. Downstream policy performance is a separate simulation experiment and cannot be inferred from MAE/RMSE alone.

After a traffic-management controller and route policy exist, planned experiments should compare them against fixed-time signal plans and baseline routes under matched simulation scenarios, demand, and seeds. Report operational outcomes such as travel time, delay, throughput, and queues. These are future comparisons, not completed experiments or current results.

## Dependencies and open decisions

This plan depends on Member 3 confirming the SUMO network, queue measurement definition and location, sampling cadence, run/scenario metadata, and available current traffic/signal fields, then producing separate timestamped simulation data. It also depends on having enough independent runs and observations to support chronological partitions and subgroup reporting.
