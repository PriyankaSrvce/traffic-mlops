"""Summarize paired SUMO controller runs without hiding completion counts."""

import argparse
import csv
import hashlib
import statistics
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"
METRICS = ("duration", "waitingTime", "timeLoss", "routeLength")
SIMULATION_HORIZON_S = 2100


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_tripinfo(path):
    if not path.is_file():
        raise FileNotFoundError(f"Missing simulation output: {path}")
    trips = ET.parse(path).getroot().findall("tripinfo")
    if not trips:
        raise ValueError(f"No completed trips in {path}")
    values = {}
    for metric in METRICS:
        raw_values = [trip.get(metric) for trip in trips]
        if any(value is None for value in raw_values):
            raise ValueError(f"Missing {metric} in trip information: {path}")
        values[metric] = [float(value) for value in raw_values]
    return {"completed_trips": len(trips), **{
        metric: statistics.mean(items) for metric, items in values.items()}}


def read_mean_csv_value(path, column):
    """Read a policy-specific queue diagnostic, or return blank if absent."""
    if not path.is_file():
        return ""
    with path.open("r", newline="", encoding="utf-8-sig") as source:
        values = [float(row[column]) for row in csv.DictReader(source)
                  if row.get(column) not in (None, "")]
    return statistics.mean(values) if values else ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--scenarios", nargs="+", choices=("low", "reference", "high"), required=True)
    parser.add_argument("--seeds", nargs="+", type=int, required=True)
    parser.add_argument("--scenario-dir", type=Path,
                        default=ROOT / "sumo" / "scenarios",
                        help="Directory containing the route files used for this matrix.")
    parser.add_argument("--by-run-output", type=Path, default=None)
    parser.add_argument("--summary-output", type=Path, default=None)
    parser.add_argument("--model-file", type=Path, default=None)
    parser.add_argument("--sumo-version", default="not recorded")
    args = parser.parse_args()

    rows = []
    network = ROOT / "sumo" / "grid_network_tls.net.xml"
    network_hash = file_sha256(network)
    model_hash = file_sha256(args.model_file) if args.model_file else ""
    for scenario in args.scenarios:
        route = args.scenario_dir / f"traffic_{scenario}.rou.xml"
        demanded = len(ET.parse(route).getroot().findall("vehicle"))
        route_hash = file_sha256(route)
        for seed in args.seeds:
            label = f"{args.run_tag}_{scenario}"
            paths = {
                "fixed": REPORT_DIR / f"fixed_{label}_seed{seed}_tripinfo.xml",
                "adaptive": REPORT_DIR / f"adaptive_{label}_seed{seed}_tripinfo.xml",
                "predictive60s": REPORT_DIR / f"predictive60s_{label}_seed{seed}_tripinfo.xml",
            }
            adaptive_decisions = REPORT_DIR / f"adaptive_{label}_seed{seed}_control_decisions.csv"
            predictive_decisions = REPORT_DIR / f"predictive60s_{label}_seed{seed}_decisions.csv"
            metrics = {policy: read_tripinfo(path) for policy, path in paths.items()}
            fixed = metrics["fixed"]
            for policy, result in metrics.items():
                row = {
                    "run_tag": args.run_tag,
                    "scenario": scenario,
                    "seed": seed,
                    "policy": policy,
                    "sumo_version": args.sumo_version,
                    "network_sha256": network_hash,
                    "route_sha256": route_hash,
                    "model_sha256": model_hash if policy == "predictive60s" else "",
                    "demanded_vehicles": demanded,
                    "completed_trips": result["completed_trips"],
                    "completion_rate": result["completed_trips"] / demanded,
                    "throughput_vehicles_per_hour": (
                        result["completed_trips"] / SIMULATION_HORIZON_S * 3600
                    ),
                    "adaptive_mean_halting_vehicles_at_decision": (
                        read_mean_csv_value(adaptive_decisions, "halting_vehicle_count")
                        if policy == "adaptive" else ""
                    ),
                    "predictive_mean_green_queue_m": (
                        read_mean_csv_value(predictive_decisions, "predicted_green_queue_m")
                        if policy == "predictive60s" else ""
                    ),
                }
                row.update({f"mean_{metric}_s" if metric != "routeLength" else "mean_routeLength_m": result[metric]
                            for metric in METRICS})
                for metric in ("duration", "waitingTime", "timeLoss"):
                    denominator = fixed[metric]
                    reduction = ((denominator - result[metric]) / denominator * 100
                                 if denominator else 0.0)
                    row[f"{metric}_reduction_pct_vs_fixed"] = reduction
                rows.append(row)

    by_run = args.by_run_output or REPORT_DIR / f"phase2_policy_comparison_{args.run_tag}_by_run.csv"
    summary = args.summary_output or REPORT_DIR / f"phase2_policy_comparison_{args.run_tag}_summary.csv"
    conflicts = [str(path) for path in (by_run, summary) if path.exists()]
    if conflicts:
        raise FileExistsError("Refusing to overwrite: " + ", ".join(conflicts))
    with by_run.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    summary_rows = []
    for scenario in args.scenarios:
        scenario_rows = [r for r in rows if r["scenario"] == scenario]
        for policy in ("fixed", "adaptive", "predictive60s"):
            subset = [r for r in scenario_rows if r["policy"] == policy]
            summary_rows.append({
                "run_tag": args.run_tag,
                "scenario": scenario,
                "policy": policy,
                "runs": len(subset),
                "mean_completion_rate": statistics.mean(r["completion_rate"] for r in subset),
                "mean_throughput_vehicles_per_hour": statistics.mean(
                    r["throughput_vehicles_per_hour"] for r in subset
                ),
                "mean_duration_s": statistics.mean(r["mean_duration_s"] for r in subset),
                "mean_waitingTime_s": statistics.mean(r["mean_waitingTime_s"] for r in subset),
                "mean_timeLoss_s": statistics.mean(r["mean_timeLoss_s"] for r in subset),
                "mean_routeLength_m": statistics.mean(r["mean_routeLength_m"] for r in subset),
                "mean_duration_reduction_pct_vs_fixed": statistics.mean(r["duration_reduction_pct_vs_fixed"] for r in subset),
                "mean_waiting_reduction_pct_vs_fixed": statistics.mean(r["waitingTime_reduction_pct_vs_fixed"] for r in subset),
                "mean_timeLoss_reduction_pct_vs_fixed": statistics.mean(r["timeLoss_reduction_pct_vs_fixed"] for r in subset),
                "sample_sd_completion_rate": statistics.stdev(r["completion_rate"] for r in subset) if len(subset) > 1 else 0.0,
                "sample_sd_throughput_vehicles_per_hour": statistics.stdev(r["throughput_vehicles_per_hour"] for r in subset) if len(subset) > 1 else 0.0,
                "sample_sd_mean_duration_s": statistics.stdev(r["mean_duration_s"] for r in subset) if len(subset) > 1 else 0.0,
                "sample_sd_mean_waitingTime_s": statistics.stdev(r["mean_waitingTime_s"] for r in subset) if len(subset) > 1 else 0.0,
                "sample_sd_mean_timeLoss_s": statistics.stdev(r["mean_timeLoss_s"] for r in subset) if len(subset) > 1 else 0.0,
                "mean_adaptive_halting_vehicles_at_decision": (
                    statistics.mean([r["adaptive_mean_halting_vehicles_at_decision"]
                                     for r in subset if r["adaptive_mean_halting_vehicles_at_decision"] != ""])
                    if policy == "adaptive" else ""
                ),
                "mean_predictive_green_queue_m": (
                    statistics.mean([r["predictive_mean_green_queue_m"] for r in subset
                                     if r["predictive_mean_green_queue_m"] != ""])
                    if policy == "predictive60s" else ""
                ),
            })
    with summary.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=summary_rows[0].keys())
        writer.writeheader()
        writer.writerows(summary_rows)

    print("Paired policy metrics written:", by_run)
    print("Scenario summary written:", summary)
    print("Trip averages use completed vehicles; compare completion rates alongside them.")


if __name__ == "__main__":
    main()
