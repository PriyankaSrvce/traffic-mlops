import csv
import math
from pathlib import Path

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
import joblib
import pandas as pd

DATA_FILE = Path("data/processed/sumo_queue_labeled_300s.csv")
MODEL_FILE = Path("models/sumo_queue_rf.joblib")
HORIZON_S = 300

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
    raise SystemExit("ERROR: Labelled dataset is empty.")

times = sorted({int(r["simulation_time_s"]) for r in rows})
test_start = times[int(len(times) * 0.8)]

# Match the earlier chronological split and purge the prediction horizon.
train_rows = [
    r for r in rows
    if int(r["simulation_time_s"]) + HORIZON_S < test_start
]
test_rows = [
    r for r in rows
    if int(r["simulation_time_s"]) >= test_start
]

if not train_rows or not test_rows:
    raise SystemExit("ERROR: Train/test split is empty.")

def make_features(records):
    result = []
    for row in records:
        item = {}
        for name in NUMERIC_FEATURES:
            item[name] = float(row[name])
        for name in CATEGORICAL_FEATURES:
            item[name] = row[name]
        result.append(item)
    return pd.DataFrame(result)

X_train = make_features(train_rows)
X_test = make_features(test_rows)
y_train = [float(r[TARGET]) for r in train_rows]
y_test = [float(r[TARGET]) for r in test_rows]

preprocessor = ColumnTransformer([
    ("numeric", "passthrough", NUMERIC_FEATURES),
    ("categorical", OneHotEncoder(handle_unknown="ignore"),
     CATEGORICAL_FEATURES),
])

model = Pipeline([
    ("preprocessor", preprocessor),
    ("regressor", RandomForestRegressor(
        n_estimators=300,
        min_samples_leaf=5,
        random_state=42,
        n_jobs=-1,
    )),
])

model.fit(X_train, y_train)
predictions = model.predict(X_test)

def report(name, predicted, actual):
    mae = mean_absolute_error(actual, predicted)
    rmse = math.sqrt(mean_squared_error(actual, predicted))
    print(f"\n{name}")
    print(f"  MAE:  {mae:.3f} m")
    print(f"  RMSE: {rmse:.3f} m")

report("Training-mean baseline",
       [sum(y_train) / len(y_train)] * len(y_test), y_test)

report("Persistence baseline",
       [float(r["queue_length_m"]) for r in test_rows], y_test)

report("Random Forest", predictions, y_test)

positive_indices = [i for i, value in enumerate(y_test) if value > 0]
print("\nTest observations with positive future queues:",
      len(positive_indices), "of", len(y_test))

if positive_indices:
    report(
        "Random Forest — positive future queues only",
        [predictions[i] for i in positive_indices],
        [y_test[i] for i in positive_indices],
    )

MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
joblib.dump(model, MODEL_FILE)

print("\nTraining observations:", len(train_rows))
print("Testing observations:", len(test_rows))
print("Test period starts at:", test_start, "seconds")
print("Saved model:", MODEL_FILE.resolve())

