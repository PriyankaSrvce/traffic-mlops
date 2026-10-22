import csv
import math
from pathlib import Path

DATA_FILE = Path("data/processed/sumo_queue_labeled_300s.csv")
HORIZON_S = 300

with DATA_FILE.open("r", newline="", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

if not rows:
    raise SystemExit("ERROR: No labelled data found.")

times = sorted({int(r["simulation_time_s"]) for r in rows})
split_index = int(len(times) * 0.8)
test_start = times[split_index]

# Training labels must finish before the test period starts.
train = [
    r for r in rows
    if int(r["simulation_time_s"]) + HORIZON_S < test_start
]
test = [
    r for r in rows
    if int(r["simulation_time_s"]) >= test_start
]

if not train or not test:
    raise SystemExit("ERROR: Empty train/test split; inspect timestamps.")

actual = [float(r["queue_length_m_t_plus_300s"]) for r in test]
current = [float(r["queue_length_m"]) for r in test]
training_mean = sum(
    float(r["queue_length_m_t_plus_300s"]) for r in train
) / len(train)

def report(name, predictions):
    errors = [p - y for p, y in zip(predictions, actual)]
    mae = sum(abs(e) for e in errors) / len(errors)
    rmse = math.sqrt(sum(e * e for e in errors) / len(errors))
    print(f"\n{name}")
    print(f"  MAE:  {mae:.3f} m")
    print(f"  RMSE: {rmse:.3f} m")

print("Dataset:", DATA_FILE)
print("Total labelled rows:", len(rows))
print("Unique observation times:", len(times))
print("Test period begins at:", test_start, "seconds")
print("Training rows after 300s purge:", len(train))
print("Testing rows:", len(test))
print("Test target zero-queue fraction:",
      f"{sum(y == 0 for y in actual) / len(actual):.1%}")

report("Persistence baseline (predict current queue)", current)
report("Training-mean baseline", [training_mean] * len(test))
