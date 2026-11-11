# Bengaluru OSM Simulation: Current Implementation and Limits

## Geography and inputs

The project includes an OpenStreetMap-derived Bengaluru corridor in `sumo/bengaluru_osm/`. OSM is the source for road geometry; converted SUMO network signal programs are not verified field timing plans. The corridor is not a complete Bengaluru network.

Demand rates, fleet shares, vehicle behavior, route choices, and departure patterns are scenario assumptions. The current generator defines two-wheelers, cars, auto-rickshaws, buses, and trucks; two seed-controlled fleet profiles use assumed shares. Vehicle departures are randomized across the configured 900-second generation interval. This implements vehicle classes and randomized departures, but it is not measured Bengaluru fleet or arrival timing. Confirm whether the professor's “initial timing delay” means this departure spread or a separate delay before/after movement. The historical daily Traffic Volume CSV does not provide real-time arrivals, fleet composition, OD flows, trajectories, or signal timing. It is not used as measured arrivals. Its license remains **unverified**.

## Queue model and control

Current queue length measures the contiguous group of downstream stopped vehicles. SUMO speed <=0.1 m/s defines stopped; neighboring stopped vehicles join if the bumper gap is <=2.5 m. Queue length includes vehicle bodies and gaps. The target is the same run/intersection/lane queue exactly 60 seconds later. This is simulation-derived, not field ground truth.

The trained model uses 11 current-state features, including assumed vehicle composition. Evaluation partitions complete runs by seed (train 7/42/2026, validation 99, test 123/31415). The model beats persistence on aggregate held-out MAE/RMSE, but its positive-queue errors are much larger. The controller implementation has fixed-time, current-state adaptive, and model-predictive modes. Controller outcomes are mixed and quality-marked; existing runs do not show predictive control is superior.

## Reproduction and evidence

See `docs/phase2_runbook.md` for commands and `reports/final_results_report.md` for metrics. Dataset quality/split files are beside the OSM v2b dataset; model evaluation metadata and Metaflow run records are in `reports/metaflow/bengaluru/`. Large network, data, and model artifacts are intended for DVC/artifact storage, not Git.

## Known limitations

- Assumed traffic and vehicle parameters are not measured/calibrated Bengaluru traffic.
- There is one OSM-derived corridor, and runs with teleports/collisions are not clean policy evidence.
- A single learned model and simulated test split do not validate performance on roads.
- Signal safety constraints and field transition plans need expert review before any operational use.
- No live signal connection or deployed public service exists.
- DVC remote configuration/status was not verified from the supplied archive; do not claim remote reproducibility.
