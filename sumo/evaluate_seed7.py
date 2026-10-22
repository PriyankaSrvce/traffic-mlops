import csv
import math
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

DATA_FILE = Path("data/processed/sumo_queue_labeled_300s_seed7.csv")
MODEL_FILE = Path("models/sumo_queue_rf.joblib")

NUMERIC_FEATURES = [
    "queue_length_m",
    "vehicle_count",
    "halting_vehicle_count",
    "mean_speed_mps",
    "phase_elapsed_s",
]

CATEGORICAL_FEATURES = [
    "intersection_id",
    "approach_id",
    "lane_id",
    "signal_phase_id",
    "signal_state",
]

TARGET = "queue_length_m_t_plus_300s"

with DATA_FILE.open("r", newline="", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

if not rows:
    raise SystemExit(f"ERROR: No rows in {DATA_FILE}")

model = joblib.load(MODEL_FILE)

features = []
actual = []
current_queue = []

for row in rows:
    item = {}
    for name in NUMERIC_FEATURES:
        item[name] = float(row[name])
    for name in CATEGORICAL_FEATURES:
        item[name] = row[name]

    features.append(item)
    actual.append(float(row[TARGET]))
    current_queue.append(float(row["queue_length_m"]))

X = pd.DataFrame(features)
predictions = model.predict(X)

# Training-mean baseline uses only the original seed-42 training period.
with Path("data/processed/sumo_queue_labeled_300s.csv").open(
    "r", newline="", encoding="utf-8-sig"
) as f:
    original_rows = list(csv.DictReader(f))

times = sorted({int(r["simulation_time_s"]) for r in original_rows})
test_start = times[int(len(times) * 0.8)]
train_rows = [
    r for r in original_rows
    if int(r["simulation_time_s"]) + 300 < test_start
]
train_targets = [float(r[TARGET]) for r in train_rows]

if not train_targets:
    raise SystemExit("ERROR: Original training targets are empty.")

training_mean = sum(train_targets) / len(train_targets)

def report(name, predicted, observed):
    mae = mean_absolute_error(observed, predicted)
    rmse = math.sqrt(mean_squared_error(observed, predicted))
    print(f"\n{name}")
    print(f"  MAE:  {mae:.3f} m")
    print(f"  RMSE: {rmse:.3f} m")

print("INDEPENDENT RUN EVALUATION")
print("Model trained on: seed 42")
print("Evaluation data: seed 7")
print("Evaluation observations:", len(rows))
print("Evaluation target positive fraction:",
      f"{sum(v > 0 for v in actual) / len(actual):.1%}")

report("Original training-mean baseline",
       [training_mean] * len(actual), actual)

report("Persistence baseline (current queue)",
       current_queue, actual)

report("Random Forest — unchanged seed-42 model",
       predictions, actual)

positive_indices = [i for i, value in enumerate(actual) if value > 0]
print("\nPositive future-queue observations:",
      len(positive_indices), "of", len(actual))

if positive_indices:
    report(
        "Random Forest — positive future queues only",
        [predictions[i] for i in positive_indices],
        [actual[i] for i in positive_indices],
    )

print("\nNote: this evaluates one independent synthetic traffic run.")
print("It does not establish real-world Bengaluru traffic performance.")
