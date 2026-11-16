# MLOps Governance Framework

Project: AI-Driven Adaptive Traffic Management Using a Digital Twin (Bengaluru OSM corridor, SUMO).
Model: 60-second-ahead queue-length predictor (hurdle model: Random Forest classifier + Random Forest regressor).

This document says **what is controlled, who decides, where the evidence lives, and why each
control exists**. Each control is enforced in code or CI where possible. A rule that only
exists on paper is easy to forget, so the rules below are built into the pipeline itself.

---

## 1. Why governance is needed for this model

The model's output is meant to inform traffic-signal timing. A wrong forecast has a real-world
cost: longer queues, wasted green time, or, in a future live deployment, unsafe signal
behaviour. Three facts make governance essential rather than optional:

1. **The training data is simulated.** Demand levels and vehicle mixes are documented
   assumptions, not field counts. Every claim must stay traceable to the exact simulation that
   produced it, or the project could overstate what it has shown.
2. **The data is 97.5 % "no queue".** A model can look accurate while missing the queues that
   matter. Acceptance therefore compares against a baseline and reports the positive-queue
   rows separately. A single headline number is not enough.
3. **Traffic changes.** New demand levels, sensor faults and road works shift the inputs.
   Without monitoring and a defined response, a model that was good at release silently decays.
   Phase 3 showed this: a demand surge raised error by 40–59 %. See §5.

---

## 2. Roles and decision rights

| Role | Responsibility | Can approve |
|---|---|---|
| **Data owner** | SUMO scenarios, demand assumptions, dataset validation, DVC data versions | New dataset versions |
| **Model owner** | Training code, Metaflow flow, evaluation, model card | Candidate models (via the quality gate) |
| **Reviewer** (another team member) | Code review of every pull request | Merging to `main` |
| **Release approver** | Deployment to Render, changing the pinned model SHA-256 | Production deployment and rollback |
| **Monitoring owner** | Runs drift checks, raises alerts, opens retraining requests | Retraining requests |

No single step moves a model to production alone. The quality gate decides *can* it be
promoted. A human decides *should* it be deployed (separation of duties).

---

## 3. Data governance

| Control | How it is enforced | Evidence | Justification |
|---|---|---|---|
| Data versioning | DVC tracks the OSM network and datasets; every dataset is identified by SHA-256 | `*.dvc` files, `dataset_sha256` in Metaflow artifacts | Any result can be reproduced from the exact bytes that produced it |
| Run isolation | Each SUMO run writes to its own folder and refuses to overwrite | `run_dataset.py`, `run_drift_scenarios.py` | Prevents silent data mixing between experiments |
| Incident quarantine | Observations within 60 s of a collision or teleport are removed | `aggregate_dataset.py`, `incident_count_run` | Simulator artefacts are not real traffic and would teach the model wrong behaviour |
| Label integrity | Each target is checked to equal the queue recorded at exactly t+60 s in the same run and lane | `aggregate_dataset.py` (mismatch count must be 0) | Prevents label leakage and off-by-one horizon bugs |
| Leakage-free split | Train/validation/test split **by whole simulation seed** (7, 42, 2026 / 99 / 123, 31415) | `evaluate_hurdle.py`, `split_by_complete_seed: true` | Rows from one run are strongly correlated; a random row split would overstate accuracy |
| Assumptions are labelled | Demand (vehicles/hour) and vehicle mix are recorded as *assumed* in metadata | `run_metadata.json`, `vehicle_composition = *_assumed` | Simulated data must never be presented as measured Bengaluru traffic |
| Synthetic faults are tagged | The sensor-fault drift batch is tagged `synthetic_fault` and is never used for training | `make_sensor_fault_batch.py` | Keeps demonstration data from leaking into model training |
| Secrets stay out of git | `.dvc/config.local`, credentials and caches are git-ignored; deployment secrets live in Render/GitHub settings | `.gitignore`, `render.yaml` (`sync: false`) | A leaked token compromises the storage and the deployment |

## 4. Model governance and versioning

### 4.1 Identity: a model *is* its SHA-256

Every model version is identified by the SHA-256 of its serialized bytes, not by a file name.
Two files with the same name can differ: in Phase 2, `72bc…` and `167b…` gave identical
predictions but different bytes. The hash removes that ambiguity.

- The API **refuses to start** if the model file's hash differs from the approved value
  (`QUEUE_MODEL_SHA256`). This was tested: a mismatched hash made the container exit with
  `ValueError`.
- The model is deserialized only **after** the hash check, because untrusted pickle files can
  execute code.
- `/api/v1/model-info` reports the served hash, so anyone can verify what is live.

### 4.2 The registry

`registry/model_versions.json` is the append-only history of every version: its hash, the
Metaflow run and dataset hash that produced it, its metrics, its stage and the reason for every
stage change. Entries are never deleted. A rejected model stays listed with the reason it was
rejected.

Stages: `rejected` → `candidate` → `approved` → `production` → `archived` (kept as rollback target).

### 4.3 Why versioning is needed (justification)

| Need | What versioning provides |
|---|---|
| **Reproducibility** | Re-running Metaflow on the same dataset hash reproduces `167b…` bit-for-bit (verified in Phase 2) |
| **Traceability / audit** | For any prediction: served SHA → registry entry → Metaflow run → dataset SHA → SUMO runs and seeds |
| **Safe rollback** | If a new version misbehaves, the previous approved SHA and its artifact URL are recorded; `scripts/model_promotion.py rollback` prints the exact settings to restore it |
| **Drift response** | Retraining creates a *new* version (v2) beside the old one. The old one is not overwritten, so both can be compared on the same data |
| **Honest reporting** | Failed versions (e.g. the single Random Forest that did not beat the baseline) stay visible, so results cannot be cherry-picked |

### 4.4 Promotion policy (quality gates)

A model reaches production only through these gates, in order:

1. **Metaflow acceptance step** (automatic). On both validation and test, the model must have MAE ≥ 5 % better than persistence, and RMSE no worse than persistence. Failing any of the four conditions stops the flow.
2. **Promotion comparison** (automatic, `scripts/model_promotion.py compare`):
   - P2: no regression on the original held-out test set (MAE ≤ production × 1.02);
   - P3: better than production on every drift evaluation set.
3. **Human approval** (manual). The release approver uploads the artifact as a GitHub Release asset, updates `QUEUE_MODEL_URL`/`QUEUE_MODEL_SHA256`, and runs the gated `deploy` job.
4. **Post-deploy verification.** `/api/v1/model-info` must report the new SHA before the registry stage becomes `production`.

**Why a 5 % margin over persistence?** Persistence ("the queue in 60 s equals the queue now")
costs nothing to run. A model that cannot clearly beat it adds complexity and risk without
benefit.

## 5. Monitoring and drift policy

| Signal | Metric | Watch | Alert | Response |
|---|---|---|---|---|
| Data drift | PSI per feature, on all rows **and** on occupied lanes | ≥ 0.10 | ≥ 0.25 | Watch: monitor closely. Alert with stable accuracy: **investigate the data pipeline**, do not retrain on suspect inputs |
| Performance drift | MAE vs approved test MAE (0.0550 m) | – | > +25 %, or model no longer beats persistence by 5 % | **Retraining recommended**: run Metaflow on refreshed data; promotion still goes through §4.4 |
| Schema / categories | Unknown categorical values, invalid numbers | any | > 1 % unknown lanes | Investigate. The API also rejects malformed requests (pydantic validation) |
| Integrity | Served SHA vs approved SHA | – | mismatch | Startup refused automatically |

**Why PSI on occupied lanes too?** About 97 % of rows are empty lanes. On all rows, a strong
demand surge moved PSI by only 0.007–0.011, which would have gone unseen. Computed on occupied
lanes, the same surge scored 0.12–0.17 (WATCH), while normal data stayed at 0.014. Monitoring
both views keeps drift on the rows that matter from being diluted.

**Why different responses for data and performance drift?** In the Phase 3 sensor-fault
experiment (speed reported in km/h instead of m/s) PSI was 0.77, a strong alert, yet MAE barely
moved (0.0550 → 0.0556). Retraining on that corrupted feed would have built the fault into the
model. The right fix is the data pipeline.

Phase 3 results (`reports/phase3_drift/drift_report.json`):

| Batch | Worst PSI | MAE | Action |
|---|---|---|---|
| Normal held-out test | 0.014 | 0.0550 | No action |
| Normal, balanced vehicle mix (matched control) | 0.053 | 0.0513 | No action |
| Demand surge 600 veh/h (unseen) | 0.123 | 0.0877 (+59 %) | Retraining recommended |
| Demand surge 720 veh/h (unseen) | 0.168 | 0.0769 (+40 %) | Retraining recommended |
| Synthetic sensor fault (km/h) | 0.765 | 0.0556 (+1 %) | Investigate data pipeline |

### 5.1 Monitoring tools and what each one is for

| Tool | Role | Evidence |
|---|---|---|
| **Evidently** | Independent, standard drift report per batch (DataDriftPreset + RegressionPreset). Confirms our PSI check with a different statistical test (Wasserstein distance) | `sumo/bengaluru_osm/evidently_drift_report.py`, `reports/phase3_drift/evidently_summary.json`, HTML reports under `/reports/evidently/…` |
| **PSI detector** | The policy engine: turns scores into OK / WATCH / ALERT and an action | `sumo/bengaluru_osm/drift_detection.py`, `drift_report.json` |
| **Python logging** | One structured line per prediction, feedback record, rejected model and failed prediction | `src/api/app.py` (logger `queue_api`), `QUEUE_API_LOG_FILE` for a rotating file |
| **Prometheus** | Scrapes `/metrics`: request counts, latency, input and prediction distributions, feedback error, model identity, last drift report | `monitoring/prometheus.yml` |
| **Grafana** | Live dashboard on those metrics | `monitoring/grafana/dashboards/traffic_mlops.json` |

**Why two drift tools?** Evidently is the recognised standard and gives a full visual report.
Our PSI detector carries the *policy* (thresholds, segments and actions) and runs inside the
pinned serving environment. Both were run on the same batches and agree: no drift on normal
data, drift in queue and vehicle-count features on occupied lanes under the surge, and drift in
speed under the sensor fault.

**Like-for-like rule.** A first Evidently run reported drift in `vehicle_composition` even on
normal data. The reference set was about half motorcycle-heavy runs, while the new batches all
use the balanced mix. That is a difference in experiment design, not traffic drift. Reference
and batches are therefore compared on the same vehicle mix, and a matched "normal, balanced mix"
control batch was added. The control shows no drift in either tool.

**Evidently's dataset-level flag.** Evidently reports "dataset drift" only when at least 50 % of
columns drift. Under the surge, 3 of 8 columns drift (37.5 %), so the dataset-level flag stays
off while the column-level results show the drift. Our policy acts on column-level results,
because three identifier columns cannot change when only demand changes.

### 5.2 Feedback and the retraining trigger

- `POST /api/v1/feedback` records the queue that was actually observed for an earlier
  prediction. Prometheus then exposes the live error of the model and of the persistence baseline.
- `scripts/retraining_trigger.py` reads the drift report and applies the policy above. A
  performance alert starts the Metaflow training flow automatically. A data-only alert never
  does. Every decision is written to `retraining_request.json` with its reasons.
- The trigger starts *training* only. Promotion still needs the quality gate, the promotion
  comparison and human approval (§4.4). **Justification:** automatic retraining is safe because
  an automatically trained model cannot reach users without passing those gates.
- Known limit: the feedback endpoint has no authentication. In this project it is used only by
  the replay script. A real deployment must authenticate feedback, or false records could
  distort the live error metrics.

## 6. Change management and CI/CD controls

| Control | Enforcement | Justification |
|---|---|---|
| All changes through pull requests with review | GitHub branch workflow | A second person catches errors and unsupported claims |
| Automated tests on every push/PR | `phase2-ci.yml` job `checks-and-image`: compile, PyTest suite, retraining-trigger check, Metaflow graph checks, Docker build, container smoke test | Broken code cannot reach `main` unnoticed |
| Deployment is a separate, manually triggered job | `deploy` job runs only on manual dispatch after checks pass; Render `autoDeployTrigger: off` | A merge alone never changes what users see |
| Pinned dependencies | `requirements-*.txt` with exact versions | The same code gives the same model (reproducibility) |
| Least-privilege container | Runs as non-root `apiuser` (UID 10001), model mounted read-only, health check | Limits damage if the service is compromised |

## 7. Responsible use, risk and limitations

- **Scope.** The model predicts *simulated* queues on one OSM-derived corridor under assumed demand. It is not validated on field data and must not control real signals without field validation.
- **Claims discipline.** The project does not claim that predictive control beats fixed-time control. That was not supported by the verified experiments. Better forecasts do not automatically mean better signal control.
- **Known weakness.** On rows where a queue will exist, persistence has lower MAE (1.90 vs 2.20 m) even though the model is better overall. This is disclosed in the model card.
- **Fairness lens for traffic.** Errors are reported per intersection, per demand level and per vehicle mix, so no corridor segment is quietly served worse.
- **Human in the loop.** Any future live use should keep the current fixed/adaptive controller as fallback, with the model advisory only.

## 8. Audit trail: where to find the evidence

| Question | Evidence |
|---|---|
| Which model is live? | `GET /api/v1/model-info` → `model_sha256` |
| Where did it come from? | `registry/model_versions.json` → Metaflow run → `dataset_sha256` |
| Did it pass the gates? | Metaflow `acceptance` step artifacts (`registry_status`, metrics) |
| Was the code tested? | GitHub Actions run history |
| Is it still healthy? | `reports/phase3_drift/drift_report.json`, Evidently reports, the `/dashboard` drift section, Grafana |
| What did it predict, and when? | API logs (`prediction lane_id=… predicted_m=… model_sha256=…`) |
| Why was retraining started? | `reports/phase3_drift/retraining_request.json` |
| Why was a version rejected or replaced? | `reason` field of each registry entry |

## 9. Review cadence

| Activity | When |
|---|---|
| Drift check on new data | Every new batch (in a live setting: daily) |
| Model card and registry review | Every promotion or rejection |
| Governance document review | Each project phase, or after any incident |
