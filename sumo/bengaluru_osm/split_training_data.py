"""Export leakage-safe train/validation/test CSVs grouped by entire seeds."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import pandas as pd

SPLITS = {"train": [7, 42, 2026], "validation": [99], "test": [123, 31415]}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=Path(__file__).resolve().parent / "datasets" / "osm_v2b" / "training_labels_incident_quarantined.csv")
    ap.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "datasets" / "osm_v2b" / "splits")
    a = ap.parse_args()
    frame = pd.read_csv(a.input)
    if frame.empty or frame[["run_id", "seed", "queue_length_m_t_plus_60s"]].isna().any().any():
        raise SystemExit("Input is empty or missing split/target values")
    if frame.groupby("run_id").seed.nunique().max() > 1:
        raise SystemExit("A run_id maps to multiple seeds; review grouping before splitting")
    if a.output_dir.exists() and any(a.output_dir.iterdir()):
        raise SystemExit(f"Refusing to overwrite nonempty split directory: {a.output_dir}")
    a.output_dir.mkdir(parents=True, exist_ok=True)
    all_seeds = set(frame.seed.astype(int).unique())
    if all_seeds != set(sum(SPLITS.values(), [])):
        raise SystemExit(f"Unexpected seed inventory: {sorted(all_seeds)}")
    manifest = {"input": str(a.input.resolve()), "input_sha256": hashlib.sha256(a.input.read_bytes()).hexdigest(), "split_unit": "complete simulation seed/run", "splits": {}}
    for name, seeds in SPLITS.items():
        part = frame[frame.seed.isin(seeds)].copy()
        if part.empty: raise SystemExit(f"Empty {name} split")
        path = a.output_dir / f"{name}.csv"
        part.to_csv(path, index=False)
        manifest["splits"][name] = {"seeds": seeds, "rows": len(part), "runs": sorted(part.run_id.unique()), "path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    (a.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({k: {"rows": v["rows"], "seeds": v["seeds"], "runs": len(v["runs"])} for k,v in manifest["splits"].items()}, indent=2))

if __name__ == "__main__": main()
