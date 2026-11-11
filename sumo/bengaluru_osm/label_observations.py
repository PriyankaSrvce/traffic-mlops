"""Attach exact +60 second queue targets within each independent SUMO run."""
import argparse
import csv
from pathlib import Path


def label_rows(rows: list[dict[str, str]], horizon: int = 60) -> list[dict[str, str]]:
    key_fields = ("run_id", "intersection_id", "lane_id")
    time_keys = [(tuple(r[k] for k in key_fields), int(float(r["time_s"]))) for r in rows]
    if len(set(time_keys)) != len(time_keys):
        raise ValueError("Duplicate run/intersection/lane/time observations; refusing ambiguous labels")
    keys = {(tuple(r[k] for k in key_fields), int(float(r["time_s"]))): r for r in rows}
    labelled = []
    for row in rows:
        future = keys.get((tuple(row[k] for k in key_fields), int(float(row["time_s"])) + horizon))
        if future is not None:
            labelled.append({**row, "queue_length_m_t_plus_60s": future["queue_length_m"]})
    return labelled


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("--horizon", type=int, default=60)
    ap.add_argument("--step", type=int, default=10)
    ap.add_argument("--output", type=Path)
    a = ap.parse_args()
    with a.input.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    labelled = label_rows(rows, a.horizon)
    out = a.output or a.input.with_name(a.input.stem.replace("observations", "labeled") + ".csv")
    fields = list(labelled[0]) if labelled else []
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(labelled)
    print(f"input_rows={len(rows)} exact_horizon_rows={len(labelled)} dropped={len(rows)-len(labelled)} output={out}")


if __name__ == "__main__":
    main()
