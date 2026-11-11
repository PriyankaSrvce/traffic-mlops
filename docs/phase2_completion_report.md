# Phase 2 Completion Status (Evidence-Based)

## Completed and locally demonstrated

- An OpenStreetMap-derived Bengaluru corridor was converted to SUMO networks. Its road geography is real OSM data; the demand, vehicle mixes, simulation behavior, and converted signal timing are assumptions.
- Queue observations, incident quarantine, exact +60-second labels, complete-seed train/validation/test partitions, persistence comparison, model-quality gates, and a Metaflow training flow are implemented. A saved local Metaflow run records the selected evaluation, data/code provenance, metrics, and artifact hash.
- The current hurdle-model test metrics are MAE 0.055003 m, RMSE 0.513549 m, R² 0.883569 on 112,176 rows, versus persistence 0.069353 m / 0.651288 m / 0.812737 on the identical rows. Positive-target subset: n=2,753, MAE 2.199547 m, RMSE 3.236860 m. The target is 60-second-ahead simulated queue length, not the Phase 1 daily traffic-volume target.
- Fixed-time, adaptive, and predictive control policies plus run-quality evaluation are implemented. The current evidence does not support a claim that predictive control is best. Runs with teleports/collisions are flagged and excluded from clean comparative claims.
- FastAPI health, model-info, and prediction routes are implemented. Local HTTP smoke checks returned a healthy response and a finite prediction with the expected model identity.
- A repeatable local Docker demo guide and captured health, model-info, sample-request, and prediction outputs are available in `docs/phase2_demo_guide.md` and `reports/demo_smoke_20261111/`.
- The full `unittest` suite passed locally: 32 tests, both in the extracted project and in a clean-checkout simulation without DVC data/model files. Both Metaflow graph checks passed in WSL/Linux, and the current Bengaluru training flow completed freshly. Docker image build and local container API smoke checks passed. These are local checks, not GitHub Actions or public deployment evidence.

## Incomplete or not independently verified

> Latest local verification on 2026-11-11 is recorded in `reports/phase2_verification_20261111.md`. It includes a 34-test pass, fresh Metaflow registry artifact/export verification, Docker build/runtime checks, and local DVC status findings. GitHub Actions run `43036696130` subsequently passed on the feature branch; public Render deployment remains unverified.

1. **DVC:** local status found project data/model/network outputs missing from this handover checkout/cache. No DVC remote was contacted. Private authentication, remote availability, and pipeline/lock reconciliation remain unverified.
2. **CI/CD:** the workflow triggers on `main`, `phase2-*` pushes, pull requests, and manual dispatch. GitHub run `43036696130` passed compile, tests, Metaflow graph checks, and Docker build on the feature branch. The gated production deployment job was skipped.
3. **Deployment:** Render is selected and the blueprint is prepared. No service, model release URL, deploy hook/service URL secrets, deployment, or hosted API is configured.
4. **Registry:** Metaflow now stores the model bytes, metadata, validation/test metrics, hash, dataset hash, and candidate status as local run artifacts; the local registry verifier and export check passed. A shared hosted Metaflow datastore is not configured.
5. **Monitoring/governance:** offline reports and monitoring utilities exist, but production prediction logging, drift alerting, feedback collection at a deployed endpoint, and triggered retraining are not demonstrated as a live service.
6. **Fresh workflow reproduction:** the current Bengaluru flow was freshly run again as Metaflow run `1794405200312669` after adding model bytes to the Metaflow artifacts. It reproduced the held-out metrics; its model hash was verified through the registry helper and exported with a matching digest. The artifact store remains local. Evidence is in the sibling `phase2-completion-evidence-20261111` folder and `reports/phase2_verification_20261111.md`.
7. **SUMO assumptions and external validity:** the current OSM generator includes five vehicle classes and seeded random departure times across the generation interval. Their fleet shares and demand rates are assumptions, not measured Bengaluru values. Confirm that the professor's “initial timing delay” feedback means this departure-time distribution; if a per-vehicle start delay or movement delay was intended, define it and run a separate experiment. One corridor does not establish calibrated Bengaluru-wide performance.

## Scope and limitations

Remaining DVC remote verification and hosted deployment steps are tracked in the latest verification report. The Phase 1 daily Traffic Volume baseline remains separate from this Phase 2 simulated queue model. Dataset license status is **unverified**. No live traffic signals, public-road deployment, or real-world predictive benefit is claimed.

See `docs/phase2_audit_report.md` for the requirement-by-requirement validation table and exact evidence status.
