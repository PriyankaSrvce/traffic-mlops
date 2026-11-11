# Historical Phase 2 Perimeter Experiment Report

> This is a separate synthetic-grid P25/P50/P75 experiment from the newer OSM-corridor model and controller work. Its findings below apply only to that experiment. Current project status and current OSM results are in `reports/final_results_report.md` and `docs/phase2_audit_report.md`.

## Scope and data relationship

This report covers a new P25/P50/P75 perimeter-only experiment. It is separate from the earlier P10/P50/P90 random-route runs; those route files and reports were preserved. The historical Bengaluru CSV contains daily traffic-volume observations, not vehicle arrivals, time-of-day flows, trajectories, queues, signal timing, or origin-destination data. It is used only to set relative synthetic demand on the existing grid network. The grid is not geographically matched to Bengaluru. The dataset license is **unverified**.

The generator calculates each road's median daily Traffic Volume, then the linear P25, P50, and P75 quantiles across those 16 road medians. The observed quantiles are 20,540.25, 26,183.00, and 34,658.125 (units unspecified). Dividing each by P50 gives demand multipliers 0.784488, 1.000000, and 1.323688. Scaled from the existing 900-vehicle reference route, the generated counts are 706, 900, and 1,191. They are relative scenario sizes, **not observed Bengaluru vehicle counts**.

## Routes and queue data

`sumo/generate_perimeter_routes.py` leaves the original random route file unchanged and creates a separate route directory. The network parser found eight inward and eight outward perimeter edges; all 64 directed entry-to-exit combinations are connected. Vehicles are distributed across the 64 pairs as evenly as possible. Departures are deterministically spaced over the baseline route's departure-time window. No explicit vehicle types are specified, so SUMO's default type is used.

The generated files are:

- `sumo/scenarios/perimeter_p25_p50_p75/traffic_low.rou.xml`
- `sumo/scenarios/perimeter_p25_p50_p75/traffic_reference.rou.xml`
- `sumo/scenarios/perimeter_p25_p50_p75/traffic_high.rou.xml`
- `reports/perimeter_demand_manifest.csv` (factors, counts, OD balance, and hashes)

All three route files loaded in SUMO 1.28.0. Queue observations were collected at five-second intervals for each scenario with seeds 7, 21, 42, and 99. The collector measures the contiguous stopped queue nearest the stop line: stopped vehicles have speed at or below 0.1 m/s, successive stopped vehicles may have a gap up to 2.5 m, and queue length is measured upstream from the stop line in metres. This is a simulator-derived heuristic, not a field-validated queue measure. Labels match the same run, intersection, and lane exactly 60 seconds later. The last 384 rows of each run were excluded because no +60-second observation existed.

## Queue prediction

The existing 60-second feature schema was retained. Model training used seeds 7 and 21 (70,688 labeled rows), validation used seed 42 (35,392 rows), and the held-out test used seed 99 (35,360 rows). Preprocessing is fitted within the training flow. The validation quality gate compared the Random Forest with persistence and passed overall, for positive queues, and in each demand scenario. The final test was run once by the Metaflow flow.

| Held-out seed 99 subset | Rows | Model MAE / RMSE (m) | Persistence MAE / RMSE (m) |
|---|---:|---:|---:|
| All targets | 35,360 | 1.147 / 2.239 | 2.671 / 4.330 |
| Positive future queues | 8,538 | 2.365 / 3.710 | 5.639 / 6.495 |

The held-out target is zero in 75.9% of rows, so the positive-queue metrics are reported separately. By scenario, overall model MAE/RMSE were 1.103/1.879 m for low, 1.097/2.003 m for reference, and 1.240/2.732 m for high. The model is a candidate passing the validation gate, not proof of field performance or improved traffic control. The run record is `reports/queue_model_metaflow_1794296235306388.json`; model SHA-256 is `ddeb3083c96c54b452005240a2ca8bf2ecab0f9a0a9a51b1823b1ad713e5ce9c`.

## Paired controller results

Fixed-time control uses the network's embedded static signal program. Adaptive control extends its active green based on current halting-vehicle counts. Predictive control uses the 60-second model and predicted green-approach queue to set green duration. For every demand level and seed, the same network and byte-identical scenario route were used across the three policies. SUMO was 1.28.0, all runs used the 2,100-second simulation horizon, and every vehicle completed.

Entries below are mean trip duration and waiting time in seconds, shown as **mean ± sample standard deviation over three seeds**. Completion was 100% in every run.

| Demand | Policy | Duration (s) | Waiting time (s) | Time loss (s) |
|---|---|---:|---:|---:|
| Low | Fixed-time | 76.01 ± 0.13 | 22.27 ± 0.25 | 33.54 ± 0.31 |
| Low | Adaptive | 65.96 ± 0.66 | 13.12 ± 0.38 | 23.50 ± 0.56 |
| Low | Predictive 60s | 71.07 ± 0.22 | 17.68 ± 0.20 | 28.61 ± 0.21 |
| Reference | Fixed-time | 77.57 ± 0.25 | 22.89 ± 0.26 | 35.16 ± 0.27 |
| Reference | Adaptive | 67.92 ± 0.16 | 14.43 ± 0.10 | 25.53 ± 0.11 |
| Reference | Predictive 60s | 71.00 ± 0.44 | 17.11 ± 0.35 | 28.59 ± 0.43 |
| High | Fixed-time | 81.63 ± 0.39 | 25.15 ± 0.17 | 39.20 ± 0.30 |
| High | Adaptive | 71.40 ± 0.53 | 16.75 ± 0.38 | 28.98 ± 0.59 |
| High | Predictive 60s | 72.67 ± 0.54 | 17.67 ± 0.56 | 30.24 ± 0.62 |

All average metrics use completed trips. As completion was complete in all policies, this does not mask differing completion rates in this matrix. Throughput is recorded as completed vehicles per 2,100-second simulation window and is therefore the same across policies within a given demand level. The adaptive policy had lower mean travel time, waiting time, and time loss than predictive control in all three scenarios. Predictive control was better than fixed-time on these metrics in this specific experiment, but this small synthetic setup is not evidence of general superiority.

The detailed run-level provenance is `reports/phase2_policy_comparison_perimeter_p25_v1_by_run_provenance.csv`. Summary and sample standard deviations are in `reports/phase2_policy_comparison_perimeter_p25_v1_summary_provenance.csv`. Plots are in `reports/phase2_perimeter_p25_v1_provenance_figures/`.

## Validation performed

- Six focused perimeter/model-contract/controller-output tests passed; three feature-pipeline tests passed; two training-pipeline tests passed; seven API tests passed with the generated model loaded; and two model-catalog hash tests passed. These were run with `unittest` in the existing Phase 1/Phase 2 environments. `pytest` is not installed in the inspected Windows Phase 2 environment, so no pytest command was run.
- All three route XML files passed short SUMO parser/simulation smoke runs.
- The full paired controller matrix completed 27/27 runs; per-run and summary CSVs were generated from those outputs.
- Metaflow completed its graph validation and all seven workflow steps. Model schema and API prediction tests loaded the generated model and produced finite, nonnegative predictions.
- At the time this perimeter experiment report was written, Docker image build, GitHub Actions execution, public deployment, and remote DVC operations had not been performed. Later local Docker verification is recorded in the current audit report. GitHub Actions, deployment, and remote DVC remain unverified. The dataset license remains unverified.

## Limits and follow-up

There is one synthetic network. Queue length is estimated using the existing stopped-vehicle heuristic. Model training data is generated under the network's default fixed signal plan; predictive/adaptive control changes the signal schedule, so controller operation introduces a distribution shift not represented in training data. The route files use one default SUMO vehicle type and evenly spaced departures. Mixed vehicle classes or alternate arrival-delay patterns require explicit agreed assumptions, separate route files, new queue data, and new model evaluation. Historical traffic values are daily and cannot calibrate actual five-minute vehicle arrivals.

This historical note about hash mismatches is superseded by the read-only checks in `docs/phase2_audit_report.md`: in the supplied archive, the checked local files and generated Phase 1 outputs match their recorded lock hashes. The DVC remote was not contacted, so remote status remains unknown. Review the current DVC configuration and verify access before relying on these data pointers.


## Integration note for the original repository

The Phase 1 DVC pipeline and the newer OSM model pipeline are represented in `dvc.yaml`/`dvc.lock`; selected local input/output hashes were checked against the lock without invoking DVC. Phase 2 orchestration uses Metaflow, while DVC entries describe selected data/model artifacts. DVC remote presence, credentials, and synchronization were not verified. No remote was contacted.
