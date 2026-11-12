# Phase 2 Execution Plan

## Objective

Productionize and demonstrate the SUMO queue-prediction workflow using Metaflow, automated checks, FastAPI, Docker, GitHub Actions, and deployment as required by the course checklist. The service target in this plan is the current SUMO model's queue length 60 seconds ahead. The historical model predicts same-day daily Traffic Volume and is a separate Phase 1 baseline.

No separate course Google Sheet or deployment-platform instruction has been provided; the available checklist is the Phase 2 objective image. Use Metaflow (not MLflow) for the Phase 2 workflow. Render is the chosen practical demo host, not a platform mandated by the instructor; no Render service or credentials are configured yet.

## Integrated execution status

The Phase 2 implementation is being completed as one integrated project. No task is being deferred to an absent teammate. Implemented and verified items are summarized in `docs/phase2_audit_report.md`; remaining tasks are GitHub Actions on a pull request, private DVC access and lock reconciliation, a hosted deployment with protected secrets, and confirmation that local Metaflow lineage meets the course registry requirement.

Execution order: (1) maintain the 60-second queue data/model contract; (2) run leakage-safe training/evaluation and paired controller experiments; (3) run unit/API checks and Metaflow graph checks; (4) build and smoke-test the container; (5) run GitHub CI; (6) configure the hosted model artifact and protected deployment service; (7) perform hosted health/prediction checks. Steps 1-5 now have recorded local or feature-branch GitHub evidence. Steps 6-7 still need the hosted model artifact, Render service configuration, protected secrets, and a real hosted smoke check.
## Required order and gates

### 1. Freeze the data and model contract

Agree on the run/scenario ID, timestamp, intersection/approach/lane IDs, current queue definition and unit, current-state features, signal state, target horizon, and missing-label policy. The current trained model is the 60-second model. The archive also has an older 300-second path; do not mix its model, CSV, or metrics into the 60-second workflow.

**Gate:** the chosen feature/target schema is recorded once, and all scripts use distinct output names for the selected horizon.

### 2. Generate and inspect repeatable scenarios

Use the prepared low/reference/high route files. They are relative synthetic demand levels, not calibrated vehicle counts. Keep route files identical across policies within a scenario. Record seed, route-file hash, network, model version, SUMO version, and run label for every simulation. The earlier grid/perimeter route family uses SUMO's default vehicle type; the separate Bengaluru OSM generator emits five vehicle types with assumed shares and seeded departure-time spread. Do not mix the route families or their results.

**Gate:** all selected route files parse, scenario counts match the manifest, and one simulation completes without errors.

### 3. Collect and label queue data

Record current queue and traffic state at the chosen sampling interval. Match each target to the same run, intersection, and lane exactly 60 seconds later. Exclude unavailable future observations. Keep run/scenario IDs. Save each collection and labeled CSV under a unique path. Never let the 60-second labeling script write to a 300-second-named destination.

**Gate:** row counts, target column, horizon, matching keys, missing-label counts, and queue units are documented.

### 4. Evaluate prediction quality

Prefer complete independent runs/scenarios in separate train, validation, and test partitions. If there are too few independent runs, split chronologically and purge any row whose future label crosses a partition boundary, including the full 60-second horizon. Fit preprocessing only on training data. Select models on validation data; use the test set once for final reporting.

Compare the 60-second model with persistence (future queue equals current queue) using MAE/RMSE in metres, both overall and for positive future queues. Report sample counts per run/scenario, intersection, and traffic condition when meaningful. Compare against the existing baseline only when the feature/target and split match. Do not claim a model improvement if it does not beat the baseline reliably.

**Gate:** a documented evaluation report identifies the data partitions, baseline, metrics, model version, and limitations.

### 5. Build the Metaflow workflow and model version record

Create Metaflow steps for input validation, preparation, splitting, training, validation-based selection, test evaluation, quality gate, and saving the approved model plus its metadata. Save the data/run identifiers, feature schema, target horizon, code version, parameters, split boundaries, metrics, and approval status with the run artifacts.

Use Metaflow artifacts and run metadata as the model's traceable version record only if the course checklist accepts that for its registry objective. Confirm this rubric interpretation with the instructor; do not silently add MLflow.

**Gate:** a teammate can inspect a successful Metaflow run and identify the model, data, code, and metrics it produced.

### 6. Add automated model-risk and quality checks

Check required fields, value types/ranges, missing values, finite predictions, nonnegative predicted queues, model loading, and agreed performance thresholds. Test the high/low scenarios for performance degradation and report failure conditions. Keep thresholds fixed before final test evaluation. Store check results with the Metaflow run.

**Gate:** invalid inputs or failed quality rules stop model approval and produce a useful explanation.

### 7. Build the inference API

FastAPI loads the approved model artifact and applies the same feature schema/preprocessing. Provide health, model-version, and prediction endpoints. Validate requests and return the queue prediction with its unit and 60-second horizon. Test valid and invalid requests. The API predicts; it does not itself operate traffic signals.

**Gate:** a documented request returns a finite prediction from the expected model version.

### 8. Package, automate, and deploy

Build a Docker image and verify the service starts and answers health and prediction requests with a versioned model artifact mounted or fetched over HTTPS with SHA-256 verification. GitHub Actions runs pinned checks and builds the image on pull requests and `main` pushes. After those checks pass on `main`, the prepared deploy job can trigger Render using GitHub Actions secrets and wait for `/health` to return HTTP 200. The Render blueprint binds the service to `PORT`, checks `/health`, and expects the model URL and SHA-256 to be configured in the Render dashboard. Keep secrets out of source files and images.

**Gate:** the team can show a passing CI run, the Docker service, and the required deployed endpoint.

### 9. Evaluate traffic policies separately

For each demand scenario and seed, compare fixed-time, adaptive, and predictive control using the same network and exact same route file. Report completed trips and completion rate alongside duration, waiting time, time loss, and route length. Compare policies within each paired scenario/seed. Prediction MAE/RMSE does not prove that a signal policy improves traffic.

**Gate:** the policy report includes run IDs, seeds, route hashes, output provenance, and paired metrics. Claims remain limited to the synthetic SUMO network.

### 10. Rehearse the in-person demonstration

Demonstrate data checks, Metaflow run/artifacts, model test results, model quality checks, API prediction, Docker, GitHub Actions, and deployment. Explain the 60-second target and synthetic-network limits. Each team member presents their contribution. Monitoring, drift detection, and retraining belong to Phase 3 unless the course checklist explicitly says otherwise.

## Current status and blockers

This section supersedes earlier scratch-state notes in this plan. The latest OSM queue-model evidence, controller quality results, local tests, Docker verification, DVC limitations, and deployment blockers are summarized in `docs/phase2_audit_report.md` and `reports/final_results_report.md`.

- The current model predicts the same-run/intersection/lane queue 60 seconds ahead using 11 features. Its test split is seeds 123/31415, distinct from train seeds 7/42/2026 and validation seed 99. Current OSM results are separate from this plan's older 18-run synthetic-grid experiment.
- The latest full unittest run passed 34 tests in WSL Python 3.12.3. Both Metaflow graph checks passed. Fresh Bengaluru run `1794405200312669` completed with matching held-out metrics and a hash-verified model artifact stored in the local Metaflow registry.
- Docker image `traffic-queue-api:phase2-final` built and ran locally. Health, model-info, and held-out positive-example prediction returned HTTP 200; the model was mounted read-only and the container ran as `apiuser`, then was removed. No image was published.
- Update 2026-11-12: GitHub run `43060494475` (manual dispatch on `main`) passed its gated deploy job, which triggered the Render deploy hook and saw `/health` 200. Hosted `/model-info` and `/predict` have not been verified, and the service URL is not recorded in the repo. The instructor has not confirmed whether the local Metaflow artifact catalog satisfies the registry rubric.
- Local `dvc status` reports data/model/network outputs missing from this checkout/cache. No remote status/synchronization was checked. DVC pipeline/lock reconciliation and remote verification remain outstanding.
- The historical dataset license is unverified. Synthetic scenario rates, vehicle composition, and signal plans are not measured Bengaluru traffic.
