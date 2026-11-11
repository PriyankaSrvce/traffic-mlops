"""Create balanced perimeter-only routes using Bengaluru road-median quartiles.

The daily Bengaluru data supplies relative scenario multipliers only. It is not
converted into observed SUMO arrival rates and is not mapped to network edges.
"""

import argparse
import csv
import hashlib
import random
import statistics
import xml.etree.ElementTree as ET
from collections import deque
from itertools import product
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRAFFIC_CSV = ROOT / "data" / "raw" / "bangalore_traffic.csv"
DEFAULT_NETWORK = ROOT / "sumo" / "grid_network_tls.net.xml"
DEFAULT_REFERENCE_ROUTE = ROOT / "sumo" / "traffic.rou.xml"
DEFAULT_OUTPUT_DIR = ROOT / "sumo" / "scenarios" / "perimeter_p25_p50_p75"
DEFAULT_MANIFEST = ROOT / "reports" / "perimeter_demand_manifest.csv"
SCENARIOS = (("low", 0.25), ("reference", 0.50), ("high", 0.75))


def linear_quantile(values, probability):
    """NumPy-style linear quantile without adding a runtime dependency."""
    ordered = sorted(values)
    if not ordered:
        raise ValueError("Cannot calculate a quantile from no values")
    if not 0 <= probability <= 1:
        raise ValueError("Quantile probability must be between 0 and 1")
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def road_level_medians(traffic_csv):
    """Return one median Traffic Volume value for each road label."""
    values_by_road = {}
    with Path(traffic_csv).open("r", newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        required = {"Road/Intersection Name", "Traffic Volume"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Traffic CSV is missing columns: {sorted(missing)}")
        for row_number, row in enumerate(reader, start=2):
            road = (row.get("Road/Intersection Name") or "").strip()
            raw_volume = row.get("Traffic Volume")
            try:
                volume = float(raw_volume)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid Traffic Volume at CSV row {row_number}") from exc
            if not road or volume < 0:
                raise ValueError(f"Invalid road or negative Traffic Volume at CSV row {row_number}")
            values_by_road.setdefault(road, []).append(volume)
    if len(values_by_road) < 4:
        raise ValueError("At least four distinct road labels are needed for quartiles")
    medians = {road: statistics.median(values) for road, values in values_by_road.items()}
    if any(value <= 0 for value in medians.values()):
        raise ValueError("Road-level median traffic volumes must all be positive")
    return medians


def demand_scenarios(road_medians, reference_vehicle_count):
    """Scale lower/reference/higher vehicle totals from P25/P50/P75 road medians."""
    if reference_vehicle_count < 1:
        raise ValueError("Reference vehicle count must be positive")
    values = list(road_medians.values())
    quantiles = {name: linear_quantile(values, p) for name, p in SCENARIOS}
    reference = quantiles["reference"]
    if reference <= 0:
        raise ValueError("P50 road-level median must be positive")
    result = {}
    for name, probability in SCENARIOS:
        multiplier = quantiles[name] / reference
        result[name] = {
            "probability": probability,
            "road_median_quantile": quantiles[name],
            "demand_multiplier": multiplier,
            "vehicle_count": int(round(reference_vehicle_count * multiplier)),
        }
    return result


def network_route_catalog(network_path):
    """Find all connected directed perimeter-entry to perimeter-exit routes."""
    root = ET.parse(network_path).getroot()
    traffic_lights = {node.get("id") for node in root.findall("tlLogic")}
    edges = {}
    adjacency = {}
    for edge in root.findall("edge"):
        if edge.get("function") == "internal":
            continue
        edge_id, from_node, to_node = edge.get("id"), edge.get("from"), edge.get("to")
        if not edge_id or not from_node or not to_node:
            continue
        edges[edge_id] = (from_node, to_node)
        adjacency.setdefault(from_node, []).append((edge_id, to_node))
    for outgoing in adjacency.values():
        outgoing.sort()

    entries = sorted(
        edge_id for edge_id, (from_node, to_node) in edges.items()
        if from_node not in traffic_lights and to_node in traffic_lights
    )
    exits = sorted(
        edge_id for edge_id, (from_node, to_node) in edges.items()
        if from_node in traffic_lights and to_node not in traffic_lights
    )
    if not entries or not exits:
        raise ValueError("Could not identify perimeter entry and exit edges around signalized junctions")

    def middle_path(start, destination):
        pending = deque([start])
        previous = {start: None}
        while pending:
            node = pending.popleft()
            if node == destination:
                break
            for edge_id, next_node in adjacency.get(node, []):
                if next_node not in previous:
                    previous[next_node] = (node, edge_id)
                    pending.append(next_node)
        if destination not in previous:
            return None
        path = []
        node = destination
        while node != start:
            parent, edge_id = previous[node]
            path.append(edge_id)
            node = parent
        return list(reversed(path))

    routes = {}
    for entry, exit_edge in product(entries, exits):
        middle = middle_path(edges[entry][1], edges[exit_edge][0])
        if middle is not None:
            route_edges = [entry, *middle, exit_edge]
            for first, second in zip(route_edges, route_edges[1:]):
                if edges[first][1] != edges[second][0]:
                    raise ValueError(f"Generated disconnected edge sequence: {first}, {second}")
            routes[(entry, exit_edge)] = route_edges
    return entries, exits, routes


def reference_departure_window(reference_route):
    root = ET.parse(reference_route).getroot()
    departures = []
    for vehicle in root.findall("vehicle"):
        try:
            departure = float(vehicle.attrib["depart"])
        except (KeyError, ValueError) as exc:
            raise ValueError("Every reference vehicle needs a numeric depart time") from exc
        if departure < 0:
            raise ValueError("Reference departures must be nonnegative")
        departures.append(departure)
    if not departures:
        raise ValueError("Reference route file contains no vehicles")
    return len(departures), min(departures), max(departures), root.attrib


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def generate_perimeter_routes(traffic_csv, network, reference_route, output_dir, manifest_path, seed=7):
    """Generate fresh scenario routes and a provenance manifest; refuse overwrites."""
    traffic_csv = Path(traffic_csv)
    network = Path(network)
    reference_route = Path(reference_route)
    output_dir = Path(output_dir)
    manifest_path = Path(manifest_path)
    if not traffic_csv.is_file() or not network.is_file() or not reference_route.is_file():
        raise FileNotFoundError("Traffic CSV, network, and reference route must all exist")

    base_count, depart_start, depart_end, root_attributes = reference_departure_window(reference_route)
    medians = road_level_medians(traffic_csv)
    scenarios = demand_scenarios(medians, base_count)
    entries, exits, pair_routes = network_route_catalog(network)
    if len(entries) != 8 or len(exits) != 8:
        raise ValueError(f"Expected eight perimeter entries and exits; found {len(entries)} and {len(exits)}")
    if len(pair_routes) != len(entries) * len(exits):
        raise ValueError(f"Only {len(pair_routes)} of the 64 perimeter OD pairs are connected")

    route_files = {name: output_dir / f"traffic_{name}.rou.xml" for name in scenarios}
    conflicts = [str(path) for path in [*route_files.values(), manifest_path] if path.exists()]
    if conflicts:
        raise FileExistsError(f"Refusing to overwrite existing output: {conflicts[0]}")

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    route_pairs = list(pair_routes)
    manifest_rows = []
    for scenario, values in scenarios.items():
        count = values["vehicle_count"]
        if count < 1:
            raise ValueError(f"Demand multiplier produced no vehicles for {scenario}")
        assignments = [route_pairs[index % len(route_pairs)] for index in range(count)]
        rng.shuffle(assignments)
        xml_root = ET.Element("routes", root_attributes)
        for index, pair in enumerate(assignments):
            if count == 1:
                departure = depart_start
            else:
                departure = depart_start + (depart_end - depart_start) * index / (count - 1)
            vehicle = ET.SubElement(
                xml_root,
                "vehicle",
                {"id": f"{scenario}_{index:06d}", "depart": f"{departure:.3f}"},
            )
            ET.SubElement(vehicle, "route", {"edges": " ".join(pair_routes[pair])})
        ET.indent(xml_root, space="  ")
        route_path = route_files[scenario]
        ET.ElementTree(xml_root).write(route_path, encoding="UTF-8", xml_declaration=True)
        pair_counts = {pair: assignments.count(pair) for pair in route_pairs}
        if max(pair_counts.values()) - min(pair_counts.values()) > 1:
            raise ValueError(f"OD pair assignment is not balanced for {scenario}")
        manifest_rows.append({
            "scenario": scenario,
            "road_median_quantile": f"P{int(values['probability'] * 100)}",
            "road_median_volume_quantile": f"{values['road_median_quantile']:.6f}",
            "demand_multiplier_vs_P50": f"{values['demand_multiplier']:.8f}",
            "reference_vehicle_count": base_count,
            "scenario_vehicle_count": count,
            "roads_in_source": len(medians),
            "connected_entry_exit_pairs": len(pair_routes),
            "vehicles_per_OD_min": min(pair_counts.values()),
            "vehicles_per_OD_max": max(pair_counts.values()),
            "departure_start_s": f"{depart_start:.3f}",
            "departure_end_s": f"{depart_end:.3f}",
            "route_seed": seed,
            "route_file": str(route_path),
            "reference_route_sha256": sha256(reference_route),
            "scenario_route_sha256": sha256(route_path),
            "interpretation": "synthetic relative demand; not calibrated Bengaluru arrivals",
        })

    with manifest_path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=manifest_rows[0].keys())
        writer.writeheader()
        writer.writerows(manifest_rows)
    return manifest_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traffic-csv", type=Path, default=DEFAULT_TRAFFIC_CSV)
    parser.add_argument("--network", type=Path, default=DEFAULT_NETWORK)
    parser.add_argument("--reference-route", type=Path, default=DEFAULT_REFERENCE_ROUTE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    rows = generate_perimeter_routes(
        args.traffic_csv, args.network, args.reference_route,
        args.output_dir, args.manifest, seed=args.seed,
    )
    print("Connected perimeter OD pairs: 64 of 64")
    for row in rows:
        print(
            f"{row['scenario']} ({row['road_median_quantile']}): "
            f"factor={row['demand_multiplier_vs_P50']}, "
            f"vehicles={row['scenario_vehicle_count']}, route={row['route_file']}"
        )
    print(f"Manifest: {args.manifest.resolve()}")


if __name__ == "__main__":
    main()
