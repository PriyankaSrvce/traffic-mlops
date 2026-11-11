"""Create deterministic low/reference/high route files without editing source routes."""

import argparse
import csv
import copy
import hashlib
import math
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "sumo" / "traffic.rou.xml"
DEFAULT_FACTORS = ROOT / "reports" / "phase2_relative_demand_factors.csv"
DEFAULT_OUTPUT_DIR = ROOT / "sumo" / "scenarios"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--factors", type=Path, default=DEFAULT_FACTORS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    with args.factors.open("r", newline="", encoding="utf-8-sig") as source:
        factors = {row["scenario"]: row for row in csv.DictReader(source)}
    if set(factors) != {"low", "reference", "high"}:
        raise SystemExit("Factor CSV must contain exactly low, reference, and high rows.")

    tree = ET.parse(args.source)
    original_root = tree.getroot()
    vehicles = original_root.findall("vehicle")
    if not vehicles or len(vehicles) != int(factors["reference"]["reference_vehicle_count"]):
        raise SystemExit("Baseline route vehicle count does not match the factor manifest.")
    if len(original_root.findall("vType")) > 0:
        raise SystemExit("This generator is scoped to the current default-type baseline; review typed fleets separately.")

    timed = []
    for vehicle in vehicles:
        try:
            depart = float(vehicle.attrib["depart"])
        except (KeyError, ValueError) as exc:
            raise SystemExit("Every baseline vehicle must have a numeric depart time.") from exc
        timed.append((depart, vehicle))
    timed.sort(key=lambda item: item[0])
    start_time, end_time = timed[0][0], timed[-1][0]

    outputs = {scenario: args.output_dir / f"traffic_{scenario}.rou.xml"
               for scenario in ("low", "reference", "high")}
    manifest_path = args.output_dir.parent.parent / "reports" / "phase2_route_manifest.csv"
    conflicts = [str(path) for path in outputs.values() if path.exists()]
    if manifest_path.exists():
        conflicts.append(str(manifest_path))
    if conflicts:
        raise SystemExit("Refusing to overwrite existing route files: " + ", ".join(conflicts))
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Preserve the reference route byte-for-byte. Resample lower/higher counts
    # systematically from the time-ordered route templates and spread departures
    # over the same interval. The same generated route is then reused by all policies.
    outputs["reference"].write_bytes(args.source.read_bytes())
    manifest_rows = []
    source_hash = sha256(args.source)
    for scenario in ("low", "high"):
        count = int(factors[scenario]["scenario_vehicle_count"])
        root = ET.Element(original_root.tag, original_root.attrib)
        for out_index in range(count):
            template_index = min(len(timed) - 1, int((out_index + 0.5) * len(timed) / count))
            template = timed[template_index][1]
            vehicle = copy.deepcopy(template)
            vehicle.set("id", f"{scenario}_{out_index:06d}")
            departure = start_time if count == 1 else start_time + (end_time - start_time) * out_index / (count - 1)
            vehicle.set("depart", f"{departure:.3f}")
            root.append(vehicle)
        ET.indent(root, space="  ")
        ET.ElementTree(root).write(outputs[scenario], encoding="UTF-8", xml_declaration=True)

    for scenario, path in outputs.items():
        count = len(ET.parse(path).getroot().findall("vehicle"))
        manifest_rows.append({
            "scenario": scenario,
            "route_file": str(path.resolve()),
            "vehicle_count": count,
            "factor_vs_reference": factors[scenario]["factor_vs_reference"],
            "baseline_route_sha256": source_hash,
            "scenario_route_sha256": sha256(path),
            "vehicle_types": "SUMO default; no explicit vType definitions",
        })

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=manifest_rows[0].keys())
        writer.writeheader()
        writer.writerows(manifest_rows)

    for row in manifest_rows:
        print(f"{row['scenario']}: {row['vehicle_count']} vehicles -> {row['route_file']}")
    print(f"Manifest: {manifest_path.resolve()}")


if __name__ == "__main__":
    main()
