import csv
import os
from pathlib import Path

INPUT_FILE = Path(os.environ.get("SUMO_INPUT_FILE", "data/processed/sumo_queue_observations.csv"))
OUTPUT_FILE = Path(os.environ.get("SUMO_LABELED_OUTPUT_FILE", "data/processed/sumo_queue_labeled_300s.csv"))
HORIZON_S = 60

with INPUT_FILE.open("r", newline="", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

if not rows:
    raise SystemExit("ERROR: Input CSV contains no observations.")

# Exact lookup: run, intersection, lane and simulation time.
queue_lookup = {}
for row in rows:
    key = (
        row["run_id"],
        row["intersection_id"],
        row["lane_id"],
        int(row["simulation_time_s"]),
    )
    if key in queue_lookup:
        raise SystemExit(f"ERROR: Duplicate source observation: {key}")
    queue_lookup[key] = float(row["queue_length_m"])

output_rows = []
missing_targets = 0

for row in rows:
    future_time = int(row["simulation_time_s"]) + HORIZON_S
    key = (
        row["run_id"],
        row["intersection_id"],
        row["lane_id"],
        future_time,
    )

    if key not in queue_lookup:
        missing_targets += 1
        continue

    labelled = dict(row)
    labelled["queue_length_m_t_plus_60s"] = queue_lookup[key]
    output_rows.append(labelled)

if not output_rows:
    raise SystemExit("ERROR: No rows have an exact future target.")

fieldnames = list(rows[0].keys()) + ["queue_length_m_t_plus_60s"]

with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(output_rows)

targets = [r["queue_length_m_t_plus_60s"] for r in output_rows]
zero_targets = sum(float(value) == 0 for value in targets)

print("Input observations:", len(rows))
print("Labelled observations:", len(output_rows))
print("Rows excluded (no exact +60s target):", missing_targets)
print("Prediction horizon:", HORIZON_S, "seconds")
print("Target zero-queue rows:", zero_targets)
print("Target positive-queue rows:", len(targets) - zero_targets)
print("Target queue minimum (m):", min(float(v) for v in targets))
print("Target queue maximum (m):", max(float(v) for v in targets))
print("Output file:", OUTPUT_FILE.resolve())



