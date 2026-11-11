# Historical Phase 2 SUMO Scenario Methodology (P10/P50/P90)

> This describes an earlier synthetic-grid scenario family. It is not the newer Bengaluru OSM corridor experiment. See `docs/bengaluru_osm_geographical_twin.md` and `reports/final_results_report.md` for current OSM-SUMO status/results.

**Vehicle-type scope:** the P10/P50/P90 and perimeter route families in this historical document use the SUMO default vehicle type. The separate OSM generator at `sumo/bengaluru_osm/generate_scenario.py` emits two-wheelers, cars, auto-rickshaws, buses, and trucks using assumed profiles, with seed-controlled departure times spread across the 900-second generation window. This is departure-time spread, not a separate driver reaction/startup delay. Do not transfer assumptions or results between these route families.

## Purpose and boundary

This scratch experiment creates repeatable low, reference, and high demand route files from the existing synthetic 900-vehicle route set. The historical Bengaluru `Traffic Volume` column is used only to estimate relative scenario factors. Its unit and relationship to SUMO vehicle arrivals are not established, so these factors are not real-world arrival rates and the SUMO network is not a calibrated Bengaluru network. The dataset license remains unverified.

## Relative factors

The raw file contains 8,936 rows, 16 distinct road labels, and 952 dates. Date-road combinations are incomplete (4–15 observed roads per date). Missing combinations are not filled with zero. For each road, the method calculates its median observed Traffic Volume. For each date with at least 8 distinct roads, it divides each observed road's daily median by that road's own median, then takes the median of those normalized ratios. Linear-interpolation P10, P50, and P90 of the resulting 819 daily indices define low, reference, and high relative demand.

The observed P10/P50/P90 normalized indices are approximately 0.747643, 0.998973, and 1.128680. Relative to P50, factors are approximately 0.748411, 1.000000, and 1.129839. Applied to the existing 900-vehicle reference route count, rounded scenario sizes are 674, 900, and 1,017 vehicles. These are synthetic relative demand levels, not conversions of daily traffic counts into SUMO arrivals.

## Route generation

The reference route file is copied byte-for-byte. Low and high files are deterministically sampled from the baseline's time-ordered vehicle route templates. Departures are spread across the same start/end interval. The generated route files have distinct names and are reused unchanged by each policy for a given scenario. Each simulation seed is recorded separately.

The baseline route file defines 900 explicit vehicles and contains no explicit `vType` definitions, so this first comparison retains SUMO's default vehicle type. Mixed vehicle types are a separate follow-up experiment: define and document the types, recollect queue data, relabel it, and retrain/evaluate the model before using that fleet with predictive control.

## Paired controller comparison

For each demand scenario and seed, run fixed-time, queue-responsive adaptive, and the current 60-second predictive controller using the same network, exact same route file, and same SUMO seed. Each run gets a unique output label; scripts stop if outputs would overwrite existing files. The executed matrix is 3 scenarios × 2 seeds × 3 policies = 18 runs.

Report completed-trip count and completion rate beside mean trip duration, waiting time, time loss, and route length. Trip averages only cover completed trips, so they must be read together with completion rate. Compare adaptive and predictive metrics to fixed-time within the same scenario and seed, then summarize the paired runs. Two seeds are preliminary evidence, not broad validation.

## Current status and limitations

- The scripts and route files were prepared and run in an isolated scratch copy. The generated XML was parsed and scenario vehicle counts were checked.
- Official portable SUMO 1.28.0 is present in the scratch runtime and its version command was verified.
- The complete paired controller matrix ran: 3 demand scenarios × 2 seeds × 3 policies = 18 runs. All vehicles completed. Results are in `reports/phase2_policy_comparison_phase2_v1_by_run.csv` and `reports/phase2_policy_comparison_phase2_v1_summary.csv`.
- Queue observations and exact 60-second labels were generated for twelve scenario/seed combinations. A local Metaflow run trained a fresh 60-second model on seeds 7 and 21, validated on seed 42, and tested once on seed 99; complete seeds are separated across partitions. The detailed metrics and run record are in `reports/phase2_experiment_report.md` and `reports/queue_model_metaflow_1794229992091473.json`.
- Earlier saved-model scoring remains available in `reports/queue_model_generalization_phase2_v1.csv` as diagnostic evidence; it is distinct from the new Metaflow model's held-out test results.
- The prior adaptive seed-21 report points to `adaptive_tripinfo.xml`, which is byte-identical to the seed-7 adaptive report. Its seed-21 provenance remains unresolved; the new runs use seed-specific names.
- The archived 60-second model used reference-demand data with SUMO's default vehicle type. The new Metaflow model was trained on low/reference/high scenarios, also using the default vehicle type. Future formal evaluation should add more complete independent runs and preferably additional networks.
- Future queue targets were zero in about 80.5%–85.9% of the six evaluated datasets. Report performance on positive future queues separately from overall MAE/RMSE.
- Existing queue measurement uses a stopped-vehicle/contiguous-gap heuristic. It is simulation-derived and not independently validated against field measurements.

## Follow-on perimeter experiment: P25/P50/P75 road medians

The P10/P50/P90 method above and its 18-run results are preserved as an earlier experiment. A separate perimeter-only experiment now uses the P25/P50/P75 quantiles of the 16 road-level daily-volume medians. The observed quantiles are 20,540.25, 26,183.00, and 34,658.125 (source units unspecified). Relative to P50, the generated factors are 0.784488, 1.000000, and 1.323688; applied to the original 900-route reference count, the synthetic route totals are 706, 900, and 1,191 vehicles. These are experimental demand settings, not actual arrival rates or vehicle counts observed in Bengaluru.

`sumo/generate_perimeter_routes.py` keeps the original `sumo/traffic.rou.xml` and existing P10/P50/P90 scenarios unchanged. It identifies eight inward and eight outward perimeter edges around B1, B2, C1, and C2, verifies all 64 directed entry/exit pairs are connected, and assigns each scenario's vehicles across those pairs so any two pair counts differ by at most one. Departures are deterministic and evenly spaced over the original reference route's departure window. The new route files and factor/hash manifest are in `sumo/scenarios/perimeter_p25_p50_p75/` and `reports/perimeter_demand_manifest.csv`.

For this new route family, queue observations were collected at five-second intervals on seeds 7, 21, 42, and 99 for all three demand levels. Labels match the same run/intersection/lane exactly 60 seconds ahead; 384 terminal rows per run without a future observation were dropped. Seeds 7 and 21 train the model, seed 42 selects it, and seed 99 is the held-out test. The new run record and metrics are in `reports/queue_model_metaflow_1794296235306388.json`; see `docs/phase2_perimeter_experiment_report.md` for full tables and caveats.

The paired controller comparison uses each exact same scenario route and seed for fixed-time, adaptive, and predictive 60-second policies (3 scenarios × 3 seeds × 3 policies = 27 runs). Per-run route/network/model hashes and SUMO version are recorded in `reports/phase2_policy_comparison_perimeter_p25_v1_by_run_provenance.csv`; means and sample standard deviations are in the matching summary CSV. These are synthetic-network results only. The predictive controller did not outperform the adaptive controller on the reported travel-time, waiting-time, or time-loss metrics.

For the perimeter P25/P50/P75 route family in this document, generated routes still use SUMO's default vehicle type and deterministic spacing; they do not use the OSM generator's mixed fleet. This is not a measured Bengaluru arrival profile. The OSM generator's separate randomized-departure/fleet-profile experiment uses different route files and model data. The dataset license remains **unverified**. See `reports/phase2_verification_20261111.md` for current DVC state.

## Commands

From the scratch project root, derive the relative factors and generate scenario route files:

```powershell
python .\sumo\derive_relative_demand.py
python .\sumo\generate_demand_routes.py
```

Run the paired policy matrix with a fresh tag (the runner uses the portable runtime beside this scratch project):

```powershell
python .\sumo\run_policy_matrix.py --run-tag phase2_run1 --seeds 7 21
```

The matrix runner requires the `sumo` executable and the 60-second model artifact. It refuses to overwrite outputs; use a new run tag for a new batch.
