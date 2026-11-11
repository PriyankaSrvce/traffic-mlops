"""Derive relative SUMO demand factors from historical daily traffic data.

The result is a relative scenario index only. It does not convert the
historical dataset into real vehicle arrival rates for the synthetic network.
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "raw" / "bangalore_traffic.csv"
DEFAULT_OUTPUT = ROOT / "reports" / "phase2_relative_demand_factors.csv"


def percentile(values, p):
    """Return a linearly interpolated percentile for values in [0, 1]."""
    ordered = sorted(values)
    if not ordered:
        raise ValueError("Cannot calculate a percentile from no values.")
    position = (len(ordered) - 1) * p
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def derive(input_path, min_roads):
    required = {"Date", "Road/Intersection Name", "Traffic Volume"}
    road_values = defaultdict(list)
    date_road_values = defaultdict(lambda: defaultdict(list))

    with input_path.open("r", newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Input CSV is missing columns: {sorted(missing)}")
        for row_number, row in enumerate(reader, start=2):
            try:
                date = row["Date"].strip()
                road = row["Road/Intersection Name"].strip()
                volume = float(row["Traffic Volume"])
            except (AttributeError, TypeError, ValueError) as exc:
                raise ValueError(f"Invalid date/road/volume at CSV row {row_number}") from exc
            if not date or not road or volume < 0:
                raise ValueError(f"Invalid date/road/volume at CSV row {row_number}")
            road_values[road].append(volume)
            date_road_values[date][road].append(volume)

    if len(road_values) < min_roads:
        raise ValueError("Too few roads to meet the requested coverage threshold.")
    road_baselines = {road: median(values) for road, values in road_values.items()}
    if any(value <= 0 for value in road_baselines.values()):
        raise ValueError("Every road must have a positive median traffic volume.")

    daily_indices = []
    for date, roads in date_road_values.items():
        if len(roads) < min_roads:
            continue
        normalized_road_values = [
            median(values) / road_baselines[road]
            for road, values in roads.items()
        ]
        daily_indices.append((date, len(roads), median(normalized_road_values)))

    if not daily_indices:
        raise ValueError("No dates meet the road-coverage threshold.")

    index_values = [row[2] for row in daily_indices]
    p10 = percentile(index_values, 0.10)
    p50 = percentile(index_values, 0.50)
    p90 = percentile(index_values, 0.90)
    if p50 <= 0:
        raise ValueError("Median normalized daily index must be positive.")

    return {
        "roads": len(road_baselines),
        "dates_total": len(date_road_values),
        "dates_used": len(daily_indices),
        "min_roads": min_roads,
        "p10": p10,
        "p50": p50,
        "p90": p90,
        "factors": {"low": p10 / p50, "reference": 1.0, "high": p90 / p50},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-roads", type=int, default=8,
                        help="Minimum distinct road records required per date.")
    parser.add_argument("--base-vehicles", type=int, default=900)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.min_roads < 1 or args.base_vehicles < 1:
        parser.error("--min-roads and --base-vehicles must be positive.")
    if args.output.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite {args.output}; pass --overwrite explicitly.")

    result = derive(args.input, args.min_roads)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=[
            "scenario", "historical_index_quantile", "historical_index_value",
            "factor_vs_reference", "reference_vehicle_count", "scenario_vehicle_count",
            "roads_in_source", "dates_used", "minimum_roads_per_date",
            "interpretation",
        ])
        writer.writeheader()
        for scenario, quantile in (("low", "p10"), ("reference", "p50"), ("high", "p90")):
            factor = result["factors"][scenario]
            writer.writerow({
                "scenario": scenario,
                "historical_index_quantile": quantile,
                "historical_index_value": f"{result[quantile]:.8f}",
                "factor_vs_reference": f"{factor:.8f}",
                "reference_vehicle_count": args.base_vehicles,
                "scenario_vehicle_count": round(args.base_vehicles * factor),
                "roads_in_source": result["roads"],
                "dates_used": result["dates_used"],
                "minimum_roads_per_date": result["min_roads"],
                "interpretation": "relative synthetic demand; not calibrated arrival rates",
            })

    print(f"Roads: {result['roads']}")
    print(f"Dates used: {result['dates_used']} of {result['dates_total']} (minimum roads/date={result['min_roads']})")
    print(f"Relative factors p10/p50/p90: {result['factors']['low']:.4f}, 1.0000, {result['factors']['high']:.4f}")
    print(f"Scenario vehicle counts from {args.base_vehicles}: "
          f"{round(args.base_vehicles * result['factors']['low'])}, {args.base_vehicles}, "
          f"{round(args.base_vehicles * result['factors']['high'])}")
    print(f"Wrote: {args.output.resolve()}")


if __name__ == "__main__":
    main()
