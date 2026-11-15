"""Induce data drift by simulating traffic conditions the model never saw in training.

Phase 3 drift experiment. Each scenario reuses the project's own pipeline steps
(generate_scenario.py -> collect_observations.py -> label_observations.py) but with a
demand level outside the training range, so the resulting observations are a
realistic "production" batch whose distribution has shifted.

Training demand range: 180 (low), 420 (medium), 540 (high) vehicles/hour.
Drift scenarios (assumptions, like all project demand values):
  surge_600  - rush-hour surge, ~11 % above the highest training demand
  surge_720  - severe surge; the level the team originally rejected for repeated gridlock

Outputs never overwrite earlier runs. Usage:
  python sumo/bengaluru_osm/run_drift_scenarios.py --output-root sumo/bengaluru_osm/runs/drift_v1
  # refresh data for retraining, using the evaluator's seed split (train/val/test seeds):
  python sumo/bengaluru_osm/run_drift_scenarios.py --seeds 7,42,2026,99,123,31415 --batch-id retrain_v2 --output-root sumo/bengaluru_osm/runs/retrain_v2
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

DRIFT_SCENARIOS = {
    "surge_600": {"vehicles_per_hour": 600, "description": "Rush-hour demand surge above the training range"},
    "surge_720": {"vehicles_per_hour": 720, "description": "Severe surge (previously rejected for gridlock)"},
}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def run(cmd: list[str], log: Path) -> None:
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    log.write_text(proc.stdout + "\n" + proc.stderr, encoding="utf-8")
    if proc.returncode:
        raise RuntimeError(f"{Path(cmd[1]).name} exit={proc.returncode}; see {log}")


def relabel_scenario(labels: Path, scenario: str) -> int:
    """Tag rows with the drift scenario name (the collector only accepts low/medium/high)."""
    with labels.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["scenario"] = scenario
    with labels.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scenarios", default="surge_600,surge_720")
    ap.add_argument("--seeds", default="777,888")
    ap.add_argument("--duration", type=int, default=900)
    ap.add_argument("--step", type=int, default=10)
    ap.add_argument("--composition-profile", default="balanced_assumed")
    ap.add_argument("--output-root", type=Path, default=HERE / "runs" / "drift_v1")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--sumo", default="sumo")
    ap.add_argument("--batch-id", default="drift_v1", help="Suffix for run IDs, e.g. retrain_v2 for refresh data")
    a = ap.parse_args()

    scenarios = [s.strip() for s in a.scenarios.split(",") if s.strip()]
    seeds = [int(s) for s in a.seeds.split(",") if s.strip()]
    if unknown := set(scenarios) - set(DRIFT_SCENARIOS):
        raise SystemExit(f"Unknown drift scenario(s): {sorted(unknown)}")
    if not (HERE / "bengaluru_osm_sim.net.xml").exists():
        raise SystemExit("bengaluru_osm_sim.net.xml is missing; fetch it with DVC (dvc pull) first.")

    root = a.output_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    index = []
    for scenario in scenarios:
        vph = DRIFT_SCENARIOS[scenario]["vehicles_per_hour"]
        for seed in seeds:
            run_id = f"bengaluru_{scenario}_seed{seed}_{a.composition_profile}_{a.batch_id}"
            out = root / f"{scenario}_seed{seed}"
            if out.exists():
                raise SystemExit(f"Refusing to overwrite existing run directory: {out}")
            out.mkdir(parents=True)
            routes, obs, labels = out / "traffic.rou.xml", out / "observations.csv", out / "labeled.csv"
            meta = {"run_id": run_id, "scenario": scenario, "drift_scenario": scenario, "batch_id": a.batch_id, "vehicles_per_hour": vph, "seed": seed,
                    "description": DRIFT_SCENARIOS[scenario]["description"], "duration_s": a.duration,
                    "vehicle_composition": a.composition_profile, "status": "running", "started_unix": time.time()}
            start = time.perf_counter()
            try:
                run([a.python, str(HERE / "generate_scenario.py"), "--scenario", "high", "--seed", str(seed),
                     "--duration", str(a.duration), "--vehicles-per-hour", str(vph),
                     "--composition-profile", a.composition_profile, "--output", str(routes)], out / "route_generation.log")
                run([a.python, str(HERE / "collect_observations.py"), "--scenario", "high", "--seed", str(seed),
                     "--step", str(a.step), "--duration", str(a.duration), "--routes", str(routes), "--run-id", run_id,
                     "--composition-profile", a.composition_profile, "--output", str(obs),
                     "--tripinfo", str(out / "tripinfo.xml"), "--statistics", str(out / "statistics.xml"),
                     "--collisions", str(out / "collisions.xml"), "--sumo", a.sumo], out / "collector.log")
                run([a.python, str(HERE / "label_observations.py"), str(obs), "--horizon", "60",
                     "--output", str(labels)], out / "labeling.log")
                meta.update(status="complete", labels=relabel_scenario(labels, scenario),
                            sha256={"routes": sha(routes), "labels": sha(labels)})
            except Exception as exc:  # keep going; record the failure honestly
                meta.update(status="failed", error=repr(exc))
            meta["elapsed_wall_s"] = round(time.perf_counter() - start, 1)
            (out / "run_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
            index.append(meta)
            print(f"{meta['status'].upper()} {run_id}: labels={meta.get('labels')} wall_s={meta['elapsed_wall_s']}", flush=True)
    (root / "drift_batch_index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
