"""Create a SYNTHETIC sensor-fault batch to demonstrate data-drift detection.

Phase 3 drift experiment. Real deployments often drift because of the data pipeline,
not the traffic: a firmware update makes a detector report speed in km/h instead of
m/s. This script copies a labelled batch and applies exactly that fault to
`mean_speed_mps` (x 3.6). Labels (the simulated future queue) are left untouched,
so the batch shows what the model would do if fed corrupted inputs.

The output is clearly tagged: scenario = "<original>_sensor_fault_kmh" and a
`synthetic_fault` column. It is never used for training.

Usage:
  python sumo/bengaluru_osm/make_sensor_fault_batch.py INPUT.csv OUTPUT.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

KMH_PER_MPS = 3.6


def apply_speed_unit_fault(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["mean_speed_mps"] = pd.to_numeric(out["mean_speed_mps"]) * KMH_PER_MPS
    out["scenario"] = out["scenario"].astype(str) + "_sensor_fault_kmh"
    out["synthetic_fault"] = "speed_reported_in_kmh"
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path)
    a = ap.parse_args()
    if a.output.exists():
        raise SystemExit(f"Refusing to overwrite {a.output}")
    a.output.parent.mkdir(parents=True, exist_ok=True)
    apply_speed_unit_fault(pd.read_csv(a.input)).to_csv(a.output, index=False)
    print(f"wrote {a.output}")


if __name__ == "__main__":
    main()
