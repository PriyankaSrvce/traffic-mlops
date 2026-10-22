# AI-Driven Adaptive Traffic Management Using a Digital Twin
## Final Experimental Results

### 1. Project Overview

This project combines historical Bengaluru traffic-volume prediction with a SUMO-based digital twin for simulated traffic management. It evaluates queue-length prediction and compares fixed-time, queue-responsive adaptive, and predictive traffic-signal control.

The traffic network and vehicle demand are synthetic. The simulation results should not be interpreted as measured improvements on real Bengaluru roads.

### 2. Historical Traffic-Volume Prediction

The historical dataset was processed using calendar and contextual features. A chronological train-test split was used to avoid training on future observations.

| Model | MAE | RMSE | R² |
|---|---:|---:|---:|
| Mean baseline | 10,544.0 | 12,846.2 | Approximately 0 |
| Linear Regression | 8,499.3 | 10,454.1 | 0.338 |
| Random Forest | 8,808.5 | 10,965.4 | 0.271 |
| XGBoost | 8,831.6 | 10,964.8 | 0.271 |

Linear Regression was selected as the champion model because it achieved the lowest test MAE and RMSE among the evaluated models. Its R² of approximately 0.338 indicates that substantial traffic-volume variation remains unexplained.

### 3. SUMO Digital Twin

A synthetic 4 × 4 grid network was generated in SUMO, with four controlled central intersections: B1, B2, C1 and C2. Each intersection has eight unique incoming lanes. Synthetic vehicle routes were generated with a fixed random seed for reproducibility.

The baseline simulation used a 90-second fixed signal cycle. The simulation recorded vehicle travel duration, waiting time, time loss and route length.

### 4. Future Queue-Length Prediction

Random Forest models were trained to estimate future lane queue length from current traffic and signal features. Future labels were created by matching observations at the same intersection and lane at the specified prediction horizon.

#### 300-second model

| Evaluation | MAE (m) | RMSE (m) |
|---|---:|---:|
| Seed 42, all test targets | 1.285 | 2.018 |
| Seed 7, independent simulation | 1.190 | 1.937 |
| Seed 21, independent simulation | 1.185 | 1.921 |
| Seed 42, positive future queues only | 3.380 | 3.674 |

The test set contains many zero-queue targets. Therefore, overall errors alone can make performance appear better than it is for lanes with actual queues.

#### 60-second model

| Evaluation | MAE (m) | RMSE (m) |
|---|---:|---:|
| Seed 42, all test targets | 1.212 | 1.969 |
| Seed 42, positive future queues only | 3.285 | 3.526 |

The 60-second model had slightly lower overall errors in its recorded evaluation. However, prediction accuracy alone does not determine the performance of a traffic-signal controller.

### 5. Traffic-Control Comparison

The following table compares the recorded mean results across two demand seeds for fixed-time and current-queue-responsive adaptive control, and one recorded seed for each predictive controller.

| Control policy | Mean trip duration (s) | Mean waiting (s) | Mean time loss (s) |
|---|---:|---:|---:|
| Fixed-time, two seeds | 89.68 | 15.36 | 27.96 |
| Adaptive, two seeds | 82.99 | 8.92 | 21.32 |
| Predictive, 300 s, seed 42 | 83.56 | 9.24 | 21.74 |
| Predictive, 60 s, seed 42 | 84.68 | 10.06 | 22.83 |

Across the two recorded seeds, adaptive control reduced average trip duration by approximately 7.46%, waiting time by 41.96%, and time loss by 23.75% relative to fixed-time control.

For seed 42, the 300-second predictive controller reduced trip duration by approximately 6.86%, waiting time by 39.32%, and time loss by 21.98% relative to its fixed-time baseline.

These are preliminary simulation findings. The predictive controller's results use one recorded seed and are not a multi-seed validation of predictive control.

### 6. Experiment Tracking and Reproducibility

MLflow experiment `traffic-digital-twin-sumo` contains 12 verified finished runs:
- Four queue-model evaluation runs.
- Seven traffic-controller evaluation runs.
- One run containing controller-comparison reports.

The project also uses Git for source-code versioning and DVC for data and pipeline reproducibility. The recorded DVC checks previously confirmed that the pipeline was up to date and the configured remote cache was synchronized.

### 7. Limitations

1. The road network and vehicle routes are synthetic rather than a calibrated representation of actual Bengaluru intersections.
2. Queue lengths are simulation-derived labels and require further validation against real measurements.
3. Queue-prediction errors are higher for positive future queues than for the full test set.
4. Predictive-controller comparisons require further evaluation across independent demand seeds.
5. The signal-control logic is a research prototype and is not safety-certified for real-world deployment.
6. No claim is made that the system is connected to live traffic signals or has been deployed on public roads.

### 8. Conclusion

The project establishes an end-to-end prototype spanning historical traffic-volume prediction, SUMO traffic simulation, future queue-length prediction, traffic-signal control experiments and MLflow tracking.

The recorded results show promising reductions in simulated travel duration, waiting time and time loss under adaptive and predictive control compared with fixed-time control. Further work should focus on broader independent-seed evaluation, improved queue prediction for congested lanes, and validation against real traffic data before considering real-world deployment.
