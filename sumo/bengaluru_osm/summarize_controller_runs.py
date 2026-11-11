"""Summarize completed paired controller runs without hiding quality failures."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd

METRICS = ["mean_travel_time_s", "mean_waiting_time_s", "mean_queue_length_m", "max_queue_length_m", "mean_speed_mps", "throughput_veh"]
POLICIES = ["fixed", "adaptive", "predictive"]
T95 = {2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+", type=Path)
    ap.add_argument("--output", required=True, type=Path)
    a = ap.parse_args()
    runs = []
    for root in a.roots:
        for path in root.rglob("run_summary.json"):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if record.get("status") in {"complete", "quality_failure"}:
                record["source_path"] = str(path)
                runs.append(record)
    frame = pd.DataFrame(runs)
    if frame.empty:
        raise SystemExit("No completed controller runs found")
    frame.to_csv(a.output.with_name("per_run_metrics.csv"), index=False)
    all_metrics = {}
    for (scenario, policy), group in frame.groupby(["scenario", "policy"]):
        all_metrics.setdefault(scenario, {})[policy] = {
            "runs": int(len(group)), "quality_failures": int(group.status.eq("quality_failure").sum()),
            "teleports": int(group.teleports.fillna(0).sum()), "collisions": int(group.collisions.fillna(0).sum()),
            **{metric: {"mean": float(group[metric].mean()), "sd": float(group[metric].std(ddof=1)) if len(group)>1 else None} for metric in METRICS}
        }
    comparisons = {}
    for scenario in sorted(frame.scenario.unique()):
        subset = frame[frame.scenario.eq(scenario)]
        idx = ["seed"]
        wide = subset.pivot_table(index=idx, columns="policy", values=METRICS, aggfunc="first")
        comparisons[scenario] = {}
        for policy in ("adaptive", "predictive"):
            comparisons[scenario][policy+"_minus_fixed"] = {}
            for metric in METRICS:
                key = (metric, policy); base = (metric, "fixed")
                if key not in wide or base not in wide: continue
                diffs = (wide[key]-wide[base]).dropna().to_numpy(float)
                n = len(diffs)
                if not n: continue
                critical = T95.get(n-1, 1.96 if n > 30 else None)
                comparisons[scenario][policy+"_minus_fixed"][metric] = {
                    "paired_n": n, "mean_difference": float(diffs.mean()),
                    "sd_difference": float(diffs.std(ddof=1)) if n>1 else None,
                    "ci95": [float(diffs.mean()-critical*diffs.std(ddof=1)/np.sqrt(n)), float(diffs.mean()+critical*diffs.std(ddof=1)/np.sqrt(n))] if n>1 and critical is not None else None,
                    "paired_seeds_with_any_quality_failure": int(subset[subset.seed.isin(wide.index)].groupby("seed").status.apply(lambda statuses: statuses.eq("quality_failure").any()).sum())
                }
    report = {"scope": "only completed runs; no imputation; includes and flags quality-failure runs", "runs": len(frame),
              "scenario_policy_summary": all_metrics, "paired_differences": comparisons}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"runs": len(frame), "scenario_policy": {s: {p: v["runs"] for p,v in pol.items()} for s,pol in all_metrics.items()}, "output": str(a.output)}, indent=2))

if __name__ == "__main__": main()
