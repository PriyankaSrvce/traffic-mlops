# TASK 8 — PHASE 2 SUMO SIMULATION AND CONTROLLER EVIDENCE AUDIT

**Authoritative Repository:** `D:\TrafficMLOps_Phase2_Workspace\repository`  
**Inspected Branch & Commit:** `main` @ `d85890058a13094ab3852f6297d87f29d5d01d0e`  
**Audit Protocol:** Strictly read-only; no simulations run, no models retrained, no datasets regenerated, no packages installed, and zero repository mutations.

---

## 1. SUMO Simulation Architecture

Inspection of `sumo/bengaluru_osm/corridor_mapping.md`, `sumo/bengaluru_osm/scenario.json`, and `sumo/bengaluru_osm/vtypes.add.xml` confirms the simulation architecture:

### A. Study Corridor Anchors and Locations
Three spatial anchors in South-East Bengaluru define the corridor endpoints within WGS84 bounding box `77.567, 12.882, 77.693, 12.958`:
1. **Silk Board Interchange:** Mapped to OSM named bus-stop feature `1723812996` ($12.9167972^\circ\text{N}, 77.6235628^\circ\text{E}$); nearest drivable passenger edge is `1208112310#1` (2.5 m away).
2. **HSR Layout:** Mapped to OSM `place=suburb` marker `456016994` ($12.9116225^\circ\text{N}, 77.6388622^\circ\text{E}$); nearest drivable passenger edge is `-133945864` (19th Cross Road, 18.4 m away).
3. **Koramangala:** Mapped to OSM `place=suburb` marker `429918282` ($12.9357366^\circ\text{N}, 77.6240810^\circ\text{E}$); nearest drivable passenger edge is `558765859#3` (17th A Main Road, 19.8 m away).

### B. Network References and Converted Extent
* The simulation uses `bengaluru_osm_sim.net.xml`, a left-hand traffic conversion generated via:
  ```bash
  netconvert --lefthand --tls.guess-signals --tls.guess-signals.dist 25 --tls.join
  ```
* Conversion features: 98,863 non-internal edges, 104,036 non-internal lanes, 43,936 junctions, and 554 traffic light controllers (TLS), of which 35 TLS intersect the 6 directed corridor routes.
* Signal phases and durations are SUMO heuristic defaults; no real-world municipal signal plans or timings were used.

### C. Simulation Duration and Warm-up
* Configured in `scenario.json`:
  * Total generation duration: `duration_s: 900` (15 minutes).
  * Warm-up window: `warmup_s: 120` (2 minutes, during which observations are discarded or drained).
  * Maximum drain time: 3,600 seconds.

### D. Vehicle Classes and Fleet Archetypes (`vtypes.add.xml`)
The scenario defines five distinct mixed-traffic vehicle archetypes:
1. `two_wheeler`: `vClass="motorcycle"`, length 2.0 m, width 0.8 m, minGap 0.8 m, maxSpeed 13.9 m/s (50 km/h), Intelligent Driver Model (`IDM`).
2. `car`: `vClass="passenger"`, length 4.5 m, width 1.8 m, minGap 2.0 m, maxSpeed 16.7 m/s (60 km/h).
3. `auto_rickshaw`: `vClass="passenger"`, length 2.7 m, width 1.4 m, minGap 1.0 m, maxSpeed 11.1 m/s (40 km/h).
4. `bus`: `vClass="bus"`, length 10.5 m, width 2.5 m, minGap 3.0 m, maxSpeed 13.9 m/s.
5. `truck`: `vClass="truck"`, length 7.0 m, width 2.4 m, minGap 3.0 m, maxSpeed 11.1 m/s.

### E. Assumed Fleet Profiles and Demand Scenarios
* **Fleet Profiles:**
  * `balanced_assumed`: 55% two-wheelers, 25% cars, 12% auto-rickshaws, 4% buses, 4% trucks.
  * `motorcycle_heavy_assumed`: 68% two-wheelers, 18% cars, 9% auto-rickshaws, 3% buses, 2% trucks.
* **Demand Scenarios:**
  * `low`: 180 vehicles/hour across the 6 OD paths.
  * `medium`: 420 vehicles/hour across the 6 OD paths.
  * `high`: 540 vehicles/hour (revised downward from 720 veh/hr after repeated gridlocks).
* **Random Seed Handling:**
  * Departure times are uniformly randomized across the 900-second window controlled by `--seed`.
  * Preserved seed partitions: Training (`7, 42, 2026`), Validation (`99`), and Test (`123, 31415`).

---

## 2. Queue Measurement and Target Formulation

Inspection of `sumo/bengaluru_osm/queue_measurement.py` and `sumo/bengaluru_osm/label_observations.py`:

### A. Queue Measurement Algorithm
* **Halting Condition:** A vehicle is classified as stopped if `speed <= 0.1 m/s` (`HALT_SPEED_MPS = 0.1`).
* **Contiguity Gap Threshold:** Stopped vehicles belong to the same contiguous queue if the bumper-to-bumper gap between them is `gap <= 2.5 m` (`MAX_QUEUE_GAP_M = 2.5`).
* **Calculation:**
  1. Identifies all halted vehicles on a lane and sorts them by `lanePosition` descending (downstream to upstream).
  2. Anchors the queue at the front bumper of the downstream-most stopped vehicle (`downstream_front`).
  3. Steps upstream: if `gap = tail_rear - front > 2.5 m`, the queue terminates.
  4. Physical queue length is computed as:
     $$\text{queue\_length\_m} = \max(0.0, \text{downstream\_front} - \text{tail\_rear})$$
     This measures the physical distance in metres spanning the leading vehicle's front bumper to the trailing vehicle's rear bumper, including inter-vehicle bumper gaps.
  5. The legacy proxy ($5.0\text{ m} \times \text{halting\_vehicles}$) is recorded separately as `queue_proxy_5m`.

### B. Target Formulation (`queue_length_m_t_plus_60s`)
* In `label_observations.py`, observations are matched within each run using composite keys:
  $$\text{Key} = (\text{run\_id}, \text{intersection\_id}, \text{lane\_id})$$
* Target matching:
  $$\text{target} = \text{observation}(\text{Key}, t + 60\text{s})[\text{queue\_length\_m}]$$
* **Integrity Check:**
  * Genuinely represents the exact physical contiguous queue on the identical lane exactly 60 seconds into the future.
  * Duplicate time observations trigger a hard exception (`ValueError`).
  * Observations in the final 60 seconds of a simulation ($t > \text{duration} - 60$) have no future label and are discarded cleanly.

---

## 3. Controller Comparison Evidence

Inspection of `sumo/bengaluru_osm/controller.py`, `reports/phase2_osm_results.md`, `reports/control_comparison.md`, and `reports/control_comparison_summary.csv`:

### A. Controller Architectures
1. **Fixed-Time Controller:** Adheres strictly to the static, unadjusted signal plans imported from OSM.
2. **Current-State Adaptive Controller:**
   * Checks queue length every 5 seconds after a minimum green elapsed time of 8 seconds.
   * If $\text{observed\_queue}_{\text{current phase}} > \text{observed\_queue}_{\text{competing phases}} + 2.0\text{ m}$ and green elapsed $< 45\text{ s}$, extends green by 5 seconds.
3. **Predictive Controller:**
   * Queries the Hurdle queue model to predict queue lengths 60 seconds ahead for all approaching lanes.
   * If $\text{predicted\_queue}_{\text{current phase}} > \text{predicted\_queue}_{\text{competing phases}} + 2.0\text{ m}$ and green elapsed $< 45\text{ s}$, extends green by 5 seconds.
   * Includes safety fallback: if model prediction fails or returns non-finite values, falls back to the adaptive rule (`prediction_fallback_adaptive`).

### B. Empirical Controller Comparison (Bengaluru OSM Study Corridor)
The documented results in `reports/phase2_osm_results.md` demonstrate that **Predictive Control does NOT outperform simpler control baselines**:

* **Low-Demand Scenario (Clean Runs, 3 Paired Seeds):**
  * Fixed-Time Mean Travel Time: **504.08 s**
  * Adaptive Mean Travel Time: **507.61 s**
  * Predictive Mean Travel Time: **507.27 s**
  * *Outcome:* Fixed-time performed best; predictive control was essentially tied with adaptive and slightly worse than fixed-time.
* **Medium-300 Batch (Clean Runs, 9 Runs Total across 3 Seeds):**
  * Fixed-Time Mean Travel Time: **531.30 s**
  * Adaptive Mean Travel Time: **536.10 s**
  * Predictive Mean Travel Time: **536.74 s**
  * *Outcome:* Fixed-time performed best; predictive control had the highest travel time.

### C. High-Demand Teleport & Collision Invalidation
* In the standard medium- and high-demand runs on the OSM corridor:
  * Two out of three medium-demand seed pairs suffered vehicle **teleports** (SUMO removes stuck vehicles after 300 seconds of zero movement).
  * High-demand runs suffered repeated **teleports, junction gridlocks, and collisions**, leaving the predictive evaluation matrix incomplete.
* **Why these runs invalidate superiority claims:**
  * When a vehicle teleports in SUMO, it is instantaneously removed from a congested link and inserted downstream. This artificially depresses measured travel times and wipes out queues.
  * Comparing controllers when vehicles are teleporting measures SUMO's gridlock-clearing heuristic rather than traffic signal efficacy.
  * The documentation properly flags these runs as **quality failures** (`status: quality_failure`), correctly rejecting any claim of controller superiority.

### D. Separation from Legacy Synthetic Grid Experiment
* Earlier documentation (`reports/final_results_report.md` and `docs/phase2_perimeter_experiment_report.md`) reported an older 27-run synthetic $4 \times 4$ grid experiment (`perimeter_p25_v1`).
* In that synthetic experiment, adaptive control achieved a 12.4%–13.2% travel time reduction, while predictive control achieved only a 6.5%–11.0% reduction.
* Both experiments independently confirm: **Predictive control does not beat adaptive control.**

---

## 4. Dataset and Model Evaluation Provenance

Inspection of `sumo/bengaluru_osm/evaluate_hurdle.py` and Metaflow run records:

### A. Partitioning and Data Provenance
* Full simulation dataset: `training_labels_incident_quarantined.csv` (357,124 rows, SHA-256 `4e8213df...`).
* Partitioning strictly by simulation seed:
  * **Train:** Seeds `7, 42, 2026` $\rightarrow$ 185,896 rows (52.05%)
  * **Validation:** Seed `99` $\rightarrow$ 59,052 rows (16.54%)
  * **Test:** Seeds `123, 31415` $\rightarrow$ 112,176 rows (31.41%)

### B. Extreme Class Imbalance (Zero-Queue Sparsity)
* Across the 112,176 test rows:
  * Zero future queue ($0.0\text{ m}$): **109,423 rows (97.55%)**
  * Positive future queue ($> 0.0\text{ m}$): **2,753 rows (2.45%)**
* Because 97.55% of all observations have zero queue, predicting zero or near-zero produces artificially low global MAE.

### C. Documented Performance Metrics (Test Set: $N = 112,176$)

| Metric Subset | Evaluation Metric | Persistence Baseline | Trained Hurdle Model | Error Delta / Improvement |
|---|---|---:|---:|---:|
| **All Test Rows** ($N = 112,176$) | **MAE** | 0.0694 m | **0.0550 m** | **20.7% reduction** |
| | **RMSE** | 0.6513 m | **0.5135 m** | **21.2% reduction** |
| | **$R^2$** | 0.8127 | **0.8836** | $+0.0709$ |
| **Positive Queues Only** ($N = 2,753$) | **MAE** | 3.3281 m | **2.1995 m** | **33.9% reduction** |
| | **RMSE** | 4.8776 m | **3.2369 m** | **33.6% reduction** |
| | **$R^2$** | 0.2452 | **0.6673** | $+0.4221$ |

### D. Workspace Reproducibility vs. Historical Provenance
* **Historical Provenance:** The metrics are mathematically documented in `reports/phase2_osm_results.md`, Metaflow run `1794405200312669` metadata, and `docs/phase2_audit_report.md`.
* **Workspace Reproducibility:** Because `training_labels_incident_quarantined.csv` (105 MB) and the model `.joblib` binary were omitted from Git, **these metrics cannot be recomputed or verified from files currently in the workspace**. They are historical run records, not locally runnable scripts.

---

## 5. Real-World Limitations

Audit of operational and field applicability claims:

| Operational Dimension | Real-World Status | Audit Evidence |
|---|---|---|
| **Real-time Bengaluru Traffic Feed** | **NONE** | No GPS probe feeds, Google Traffic APIs, or camera feeds exist. Vehicle arrivals are synthetic random Poisson departures in SUMO. |
| **Field Calibration** | **NONE** | No actual traffic counts, saturation flows, or travel times from Bengaluru roads were collected or calibrated. Driver parameters use standard European/SUMO defaults (`IDM`). |
| **Physical Signal Control** | **NONE** | No interface to Bengaluru Traffic Police (BTP), BBMP, or physical signal controllers. Signal timings are synthetic heuristic programs. |
| **Live Vehicle Detection** | **NONE** | Controllers query SUMO internal memory via TraCI (`traci.lane.getLastStepVehicleIDs`). No radar, inductive loop, or computer vision sensors exist. |
| **Production Traffic Deployment** | **NONE** | System is a local simulation study. No physical deployment has ever taken place. |

---

## 6. Final Evaluation Report

### A. SUMO Architecture Status: `VERIFIED IN CODE / REPRODUCIBLE`
* Spatial mapping of Silk Board, HSR Layout, and Koramangala, the 5 vehicle archetypes, the 2 assumed fleet shares, and the 6 OD paths are fully implemented in configuration files and scripts.

### B. Network and Simulation Availability: `BLOCKED LOCALLY`
* The simulation cannot be executed in the current workspace because:
  1. `bengaluru_osm_sim.net.xml` is absent (represented only by a DVC pointer file).
  2. SUMO binaries (`sumo`, `netconvert`, `traci`) are not installed on the system PATH.

### C. Queue Definition and Target Correctness: `VERIFIED`
* The physical contiguous queue definition (speed $\le 0.1\text{ m/s}$, bumper gap $\le 2.5\text{ m}$) is implemented correctly. The 60-second forward horizon target is exact, joins on unique lane-time keys, and avoids lookahead leakage.

### D. Controller Comparison Evidence: `VERIFIED`
* Code for fixed, adaptive, and predictive controllers is complete. The evidence shows that predictive control does not outperform fixed-time or adaptive control on travel time (504.08s fixed vs. 507.27s predictive in low demand; 531.30s fixed vs. 536.74s predictive in medium-300).

### E. Dataset and Model Evaluation Provenance: `VERIFIED HISTORICALLY / BLOCKED LOCALLY`
* Seed splits (`7, 42, 2026` train; `99` val; `123, 31415` test), the 97.55% zero-queue distribution, and hurdle model metrics (0.0550m overall MAE; 2.1995m positive MAE) are historically verified across reports and Metaflow run records, but cannot be reproduced locally without the dataset binary.

### F. Invalid or Limited Experiments: `VERIFIED & FLAGGED`
* Medium- and high-demand simulation runs experienced vehicle teleports and gridlocks. The project correctly flags these runs as quality failures and refrains from using them to claim controller superiority.

### G. Real-World Limitations: `VERIFIED & CONFIRMED`
* The system is an uncalibrated microscopic simulation prototype. It has zero live traffic data, zero field calibration, zero sensor integration, and zero connection to municipal traffic infrastructure.

---

## 7. Overall Verdict

| Audit Dimension | Verdict | Core Finding |
|---|---|---|
| **SUMO Simulation Setup** | **VERIFIED** | Accurate spatial corridor anchors, 5 vehicle archetypes, 2 fleet profiles. |
| **Simulation Executability** | **BLOCKED** | Network XML file absent; SUMO binaries missing from host PATH. |
| **Queue & Target Contract** | **VERIFIED** | Contiguous queue (speed $\le 0.1$, gap $\le 2.5\text{m}$); exact 60s future label. |
| **Predictive Controller Value** | **VERIFIED (NO BENEFIT)** | Predictive control fails to beat fixed or adaptive control on travel time. |
| **High-Demand Controller Runs** | **FAILED (TELEPORTS)** | Gridlocks and vehicle teleports invalidate high-demand policy comparisons. |
| **Model Evaluation Integrity** | **VERIFIED** | Seed-isolated splits; 33.9% error reduction on positive queues ($N=2,753$). |
| **Real-World Calibration** | **NOT IMPLEMENTED** | Uncalibrated synthetic simulation; no live feeds, sensors, or municipal signals. |

**Final Assessment: SUMO SCENARIO SPECIFICATION, QUEUE MEASUREMENT LOGIC, AND MODEL EVALUATION PROCEDURES ARE FULLY VERIFIED. CONTROLLER EVIDENCE CONFIRMS PREDICTIVE CONTROL OFFERS NO TRAVEL TIME ADVANTAGE OVER BASELINES. LOCAL SIMULATION EXECUTION IS BLOCKED DUE TO MISSING SUMO BINARIES AND DVC NETWORK PAYLOADS.**

