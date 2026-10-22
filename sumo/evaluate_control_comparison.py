import csv
import xml.etree.ElementTree as ET
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"

RUNS = {
    7: {
        "fixed": REPORTS / "fixed_seed7_tripinfo.xml",
        "adaptive": REPORTS / "adaptive_seed7_tripinfo.xml",
    },
    21: {
        "fixed": REPORTS / "fixed_seed21_tripinfo.xml",
        "adaptive": REPORTS / "adaptive_tripinfo.xml",
    },
}

METRICS = {
    "duration": "Average trip duration (s)",
    "waitingTime": "Average waiting time (s)",
    "timeLoss": "Average time loss (s)",
    "routeLength": "Average route length (m)",
}


def read_tripinfo(path):
    if not path.exists():
        raise FileNotFoundError(f"Missing simulation output: {path}")

    root = ET.parse(path).getroot()
    trips = root.findall("tripinfo")

    if not trips:
        raise ValueError(f"No completed trips found in {path}")

    result = {"completed_trips": len(trips)}

    for field in METRICS:
        values = [float(trip.get(field, "0")) for trip in trips]
        result[field] = mean(values)

    return result


def percent_reduction(fixed, adaptive):
    if fixed == 0:
        return 0.0
    return (fixed - adaptive) / fixed * 100


def main():
    rows = []

    for seed, files in RUNS.items():
        fixed = read_tripinfo(files["fixed"])
        adaptive = read_tripinfo(files["adaptive"])

        row = {
            "seed": seed,
            "fixed_completed_trips": fixed["completed_trips"],
            "adaptive_completed_trips": adaptive["completed_trips"],
        }

        for field, label in METRICS.items():
            row[f"fixed_{field}"] = fixed[field]
            row[f"adaptive_{field}"] = adaptive[field]
            row[f"{field}_reduction_pct"] = percent_reduction(
                fixed[field], adaptive[field]
            )

        rows.append(row)

    by_seed_path = REPORTS / "control_comparison_by_seed.csv"
    with by_seed_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: round(value, 4) if isinstance(value, float) else value
                for key, value in row.items()
            })

    metric_fields = list(METRICS.keys())
    summary = {}

    for field in metric_fields:
        fixed_values = [row[f"fixed_{field}"] for row in rows]
        adaptive_values = [row[f"adaptive_{field}"] for row in rows]
        summary[field] = {
            "fixed_mean": mean(fixed_values),
            "adaptive_mean": mean(adaptive_values),
            "reduction_pct": percent_reduction(
                mean(fixed_values), mean(adaptive_values)
            ),
        }

    summary_path = REPORTS / "control_comparison_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([
            "metric", "fixed_time_mean", "adaptive_mean", "reduction_pct"
        ])
        for field, label in METRICS.items():
            values = summary[field]
            writer.writerow([
                label,
                round(values["fixed_mean"], 4),
                round(values["adaptive_mean"], 4),
                round(values["reduction_pct"], 4),
            ])

    markdown_path = REPORTS / "control_comparison.md"
    with markdown_path.open("w", encoding="utf-8") as file:
        file.write("# Fixed-Time vs Adaptive Traffic Control\n\n")
        file.write(
            "Results from two SUMO simulation seeds on the same synthetic "
            "network and route file. These are simulation results, not "
            "real-world Bengaluru performance measurements.\n\n"
        )

        file.write("## Results by seed\n\n")
        file.write(
            "| Seed | Control | Completed trips | Duration (s) | "
            "Waiting (s) | Time loss (s) | Route length (m) |\n"
        )
        file.write("|---:|---|---:|---:|---:|---:|---:|\n")

        for row in rows:
            for control in ("fixed", "adaptive"):
                file.write(
                    f"| {row['seed']} | {control.title()} | "
                    f"{row[f'{control}_completed_trips']} | "
                    f"{row[f'{control}_duration']:.2f} | "
                    f"{row[f'{control}_waitingTime']:.2f} | "
                    f"{row[f'{control}_timeLoss']:.2f} | "
                    f"{row[f'{control}_routeLength']:.2f} |\n"
                )

        file.write("\n## Mean results across seeds\n\n")
        file.write(
            "| Metric | Fixed-time mean | Adaptive mean | Reduction |\n"
        )
        file.write("|---|---:|---:|---:|\n")

        for field, label in METRICS.items():
            values = summary[field]
            file.write(
                f"| {label} | {values['fixed_mean']:.2f} | "
                f"{values['adaptive_mean']:.2f} | "
                f"{values['reduction_pct']:.2f}% |\n"
            )

        file.write(
            "\n**Interpretation:** Lower duration, waiting time and time "
            "loss indicate improvement. Route length should remain similar "
            "because the compared simulations use the same predetermined "
            "routes. Only two seeds have been evaluated, so these results "
            "are preliminary.\n"
        )

    print("Evaluation complete.")
    print(f"Per-seed results: {by_seed_path.relative_to(ROOT)}")
    print(f"Summary CSV:      {summary_path.relative_to(ROOT)}")
    print(f"Markdown report:  {markdown_path.relative_to(ROOT)}")
    print("\nMEAN RESULTS ACROSS SEEDS")
    for field, label in METRICS.items():
        values = summary[field]
        print(
            f"{label}: fixed={values['fixed_mean']:.2f}, "
            f"adaptive={values['adaptive_mean']:.2f}, "
            f"reduction={values['reduction_pct']:.2f}%"
        )


if __name__ == "__main__":
    main()
