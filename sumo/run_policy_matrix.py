"""Run fixed, adaptive, and 60-second predictive policies on paired inputs.

This runner refuses to start if any expected output already exists. Use a new
--run-tag for a fresh set of results rather than overwriting previous runs.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMO_DIR = ROOT / "sumo"
REPORT_DIR = ROOT / "reports"
SCENARIO_DIR = SUMO_DIR / "scenarios"
DEFAULT_SUMO_HOME = ROOT.parent / "runtime" / "sumo-win64-1.28.0"


def expected_outputs(policy, label, seed):
    if policy == "fixed":
        prefix = REPORT_DIR / f"fixed_{label}_seed{seed}"
        return [Path(str(prefix) + "_tripinfo.xml"), Path(str(prefix) + "_summary.xml")]
    if policy == "adaptive":
        prefix = REPORT_DIR / f"adaptive_{label}_seed{seed}"
        return [Path(str(prefix) + suffix) for suffix in (
            "_tripinfo.xml", "_summary.xml", "_control_decisions.csv")]
    prefix = REPORT_DIR / f"predictive60s_{label}_seed{seed}"
    return [Path(str(prefix) + suffix) for suffix in (
        "_tripinfo.xml", "_summary.xml", "_decisions.csv", "_predictions.csv")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-tag", default="phase2", help="Unique label prefix for this batch.")
    parser.add_argument("--scenarios", nargs="+", choices=("low", "reference", "high"),
                        default=("low", "reference", "high"))
    parser.add_argument("--seeds", nargs="+", type=int, default=(7, 21))
    parser.add_argument("--scenario-dir", type=Path, default=SCENARIO_DIR,
                        help="Directory containing traffic_{low,reference,high}.rou.xml.")
    parser.add_argument("--model-file", type=Path, default=Path(os.environ.get(
        "SUMO_MODEL_FILE", str(ROOT / "models" / "sumo_queue_rf_60s.joblib"))),
        help="Approved 60-second queue model to use for predictive runs.")
    parser.add_argument("--sumo-home", type=Path,
                        default=Path(os.environ.get("SUMO_HOME", DEFAULT_SUMO_HOME)))
    parser.add_argument("--sumo-binary", default=os.environ.get(
        "SUMO_BINARY", str(DEFAULT_SUMO_HOME / "bin" / "sumo.exe")))
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.run_tag):
        parser.error("--run-tag may contain only letters, numbers, '_' and '-'.")
    sumo_home = args.sumo_home.resolve()
    if not (sumo_home / "tools").is_dir():
        raise FileNotFoundError(f"SUMO tools directory not found under: {sumo_home}")
    if not (Path(args.sumo_binary).is_file() or shutil.which(args.sumo_binary)):
        raise SystemExit(f"SUMO executable not found: {args.sumo_binary}")
    required = (
        SUMO_DIR / "grid_network_tls.net.xml",
        SUMO_DIR / "run_fixed_simulation.py",
        SUMO_DIR / "run_adaptive_simulation.py",
        SUMO_DIR / "run_predictive_simulation_60s.py",
        args.model_file,
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing required project files: " + ", ".join(missing))

    policies = ("fixed", "adaptive", "predictive60s")
    jobs = []
    for scenario in args.scenarios:
        route = args.scenario_dir / f"traffic_{scenario}.rou.xml"
        if not route.is_file():
            raise FileNotFoundError(f"Scenario route not found: {route}")
        for seed in args.seeds:
            label = f"{args.run_tag}_{scenario}"
            for policy in policies:
                jobs.append((scenario, seed, label, policy, route))

    outputs = [path for _, seed, label, policy, _ in jobs
               for path in expected_outputs(policy, label, seed)]
    evaluation_outputs = [
        REPORT_DIR / f"phase2_policy_comparison_{args.run_tag}_by_run.csv",
        REPORT_DIR / f"phase2_policy_comparison_{args.run_tag}_summary.csv",
    ]
    outputs.extend(evaluation_outputs)
    existing = [str(path) for path in outputs if path.exists()]
    if existing:
        raise SystemExit("Refusing to overwrite existing outputs; choose a new --run-tag. First conflict: " + existing[0])

    scripts = {
        "fixed": SUMO_DIR / "run_fixed_simulation.py",
        "adaptive": SUMO_DIR / "run_adaptive_simulation.py",
        "predictive60s": SUMO_DIR / "run_predictive_simulation_60s.py",
    }
    env_base = os.environ.copy()
    env_base["SUMO_BINARY"] = args.sumo_binary
    env_base["SUMO_HOME"] = str(sumo_home)
    sumo_tools = str(sumo_home / "tools")
    prior_pythonpath = env_base.get("PYTHONPATH", "")
    env_base["PYTHONPATH"] = sumo_tools + (os.pathsep + prior_pythonpath if prior_pythonpath else "")
    for index, (scenario, seed, label, policy, route) in enumerate(jobs, start=1):
        env = env_base.copy()
        env["SUMO_ROUTE_FILE"] = str(route.resolve())
        env["SUMO_RUN_LABEL"] = label
        env["SUMO_SEED"] = str(seed)
        env["SUMO_MODEL_FILE"] = str(args.model_file.resolve())
        print(f"[{index}/{len(jobs)}] {scenario} / seed {seed} / {policy}")
        subprocess.run([sys.executable, str(scripts[policy])], cwd=ROOT, env=env, check=True)

    version_result = subprocess.run(
        [args.sumo_binary, "--version"], check=True,
        capture_output=True, text=True,
    )
    sumo_version = next((line.strip() for line in version_result.stdout.splitlines()
                         if line.strip()), "unknown")
    eval_command = [
        sys.executable, str(SUMO_DIR / "evaluate_policy_matrix.py"),
        "--run-tag", args.run_tag,
        "--scenarios", *args.scenarios,
        "--seeds", *(str(seed) for seed in args.seeds),
        "--scenario-dir", str(args.scenario_dir.resolve()),
        "--model-file", str(args.model_file.resolve()),
        "--sumo-version", sumo_version,
    ]
    subprocess.run(eval_command, cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
