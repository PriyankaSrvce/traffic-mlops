"""Build a refreshed training dataset = approved dataset + new incident-quarantined runs.

Phase 3 retraining. The original rows are kept unchanged (so the model still learns normal
traffic); the refresh rows come from aggregate_dataset.py run on the new SUMO runs. Seeds in
the refresh runs follow the evaluator's split (train 7/42/2026, validation 99, test 123/31415),
so evaluate_hurdle.py splits the merged table exactly as before.

Writes the merged CSV and a manifest with both input hashes and the output hash.

Usage:
  python sumo/bengaluru_osm/build_refresh_dataset.py --base BASE.csv --refresh REFRESH.csv --output OUT.csv
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

KEY = ["run_id", "intersection_id", "lane_id", "time_s"]
SPLIT_SEEDS = {7, 42, 2026, 99, 123, 31415}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def merge(base: pd.DataFrame, refresh: pd.DataFrame) -> pd.DataFrame:
    if missing := set(base.columns) - set(refresh.columns):
        raise ValueError(f"Refresh data is missing columns: {sorted(missing)}")
    if extra := set(refresh.seed.astype(int)) - SPLIT_SEEDS:
        raise ValueError(f"Refresh seeds outside the evaluator split: {sorted(extra)}")
    if overlap := set(base.run_id) & set(refresh.run_id):
        raise ValueError(f"run_id collision between base and refresh: {sorted(overlap)[:3]}")
    merged = pd.concat([base, refresh[base.columns]], ignore_index=True)
    if merged.duplicated(KEY).any():
        raise ValueError("Duplicate observation keys after merge")
    return merged


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--refresh", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    if a.output.exists():
        raise SystemExit(f"Refusing to overwrite {a.output}")
    base, refresh = pd.read_csv(a.base), pd.read_csv(a.refresh)
    merged = merge(base, refresh)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(a.output, index=False)
    manifest = {"base": {"path": a.base.name, "sha256": sha(a.base), "rows": len(base), "runs": int(base.run_id.nunique())},
                "refresh": {"path": a.refresh.name, "sha256": sha(a.refresh), "rows": len(refresh),
                            "runs": int(refresh.run_id.nunique()), "scenarios": sorted(refresh.scenario.unique().tolist())},
                "output": {"path": a.output.name, "sha256": sha(a.output), "rows": len(merged), "runs": int(merged.run_id.nunique())}}
    a.output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
