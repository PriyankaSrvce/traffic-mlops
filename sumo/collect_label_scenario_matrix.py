"""Collect and label held-out 60-second queue data for each scenario/seed."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMO_DIR = ROOT / "sumo"
DATA_DIR = ROOT / "data" / "processed"
DEFAULT_SUMO_HOME = ROOT.parent / "runtime" / "sumo-win64-1.28.0"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-tag", default="phase2_v1")
    parser.add_argument("--scenarios", nargs="+", choices=("low", "reference", "high"),
                        default=("low", "reference", "high"))
    parser.add_argument("--seeds", nargs="+", type=int, default=(7, 21))
    parser.add_argument("--scenario-dir", type=Path, default=SUMO_DIR / "scenarios",
                        help="Directory containing traffic_{low,reference,high}.rou.xml.")
    parser.add_argument("--sumo-home", type=Path, default=DEFAULT_SUMO_HOME)
    parser.add_argument("--sumo-binary", default=str(DEFAULT_SUMO_HOME / "bin" / "sumo.exe"))
    args = parser.parse_args()

    jobs = []
    for scenario in args.scenarios:
        route = args.scenario_dir / f"traffic_{scenario}.rou.xml"
        if not route.is_file():
            raise FileNotFoundError(f"Scenario route not found: {route}")
        for seed in args.seeds:
            run_id = f"{args.run_tag}_{scenario}_seed{seed}"
            observations = DATA_DIR / f"queue_observations_{run_id}.csv"
            labeled = DATA_DIR / f"queue_labeled_60s_{run_id}.csv"
            jobs.append((scenario, seed, run_id, route, observations, labeled, True))

    existing = [str(path) for *_, obs, lab, collect in jobs
                for path in ((obs, lab) if collect else (lab,)) if path.exists()]
    if existing:
        raise SystemExit("Refusing to overwrite existing queue data: " + existing[0])

    home = args.sumo_home.resolve()
    tools = home / "tools"
    if not tools.is_dir():
        raise FileNotFoundError(f"SUMO tools directory not found: {tools}")
    env_base = os.environ.copy()
    env_base["SUMO_HOME"] = str(home)
    env_base["SUMO_BINARY"] = args.sumo_binary
    old_pythonpath = env_base.get("PYTHONPATH", "")
    env_base["PYTHONPATH"] = str(tools) + (os.pathsep + old_pythonpath if old_pythonpath else "")

    for index, (scenario, seed, run_id, route, observations, labeled, collect) in enumerate(jobs, start=1):
        env = env_base.copy()
        if collect:
            env.update({
                "SUMO_ROUTE_FILE": str(route.resolve()),
                "SUMO_SEED": str(seed),
                "SUMO_RUN_ID": run_id,
                "SUMO_OUTPUT_FILE": str(observations.resolve()),
            })
            print(f"[{index}/{len(jobs)}] Collecting {scenario}, seed {seed}")
            subprocess.run([sys.executable, str(SUMO_DIR / "collect_queue_data.py")],
                           cwd=ROOT, env=env, check=True)
        else:
            print(f"[{index}/{len(jobs)}] Reusing archived reference observations for seed {seed}")
        env["SUMO_INPUT_FILE"] = str(observations.resolve())
        env["SUMO_LABELED_OUTPUT_FILE"] = str(labeled.resolve())
        print(f"[{index}/{len(jobs)}] Creating exact +60s labels for {scenario}, seed {seed}")
        subprocess.run([sys.executable, str(SUMO_DIR / "label_queue_data_60s.py")],
                       cwd=ROOT, env=env, check=True)


if __name__ == "__main__":
    main()
