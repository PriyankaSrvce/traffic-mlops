"""Generate reproducible anchor-to-anchor routes on the imported OSM network."""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import sumolib

HERE = Path(__file__).resolve().parent
VEH_TYPES = ("two_wheeler", "car", "auto_rickshaw", "bus", "truck")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=("low", "medium", "high"), default="low")
    parser.add_argument("--seed", type=int, default=21)
    parser.add_argument("--duration", type=int, default=900)
    parser.add_argument("--vehicles-per-hour", type=int, default=None,
                        help="Override the scenario's assumed rate for a separate experiment.")
    parser.add_argument("--composition-profile", default="balanced_assumed")
    parser.add_argument("--output", type=Path, default=HERE / "traffic.rou.xml")
    args = parser.parse_args()
    meta = json.loads((HERE / "scenario.json").read_text(encoding="utf-8"))
    net = sumolib.net.readNet(str(HERE / meta["network"]), withInternal=False)
    anchors = {name: net.getEdge(item["edge"]) for name, item in meta["anchors"].items()}
    demand = args.vehicles_per_hour if args.vehicles_per_hour is not None else meta["demand"][args.scenario]["vehicles_per_hour"]
    if demand <= 0:
        raise SystemExit("vehicles-per-hour must be a positive integer")
    if args.composition_profile not in meta["vehicle_composition_profiles"]:
        raise SystemExit(f"Unknown composition profile: {args.composition_profile}")
    shares = meta["vehicle_composition_profiles"][args.composition_profile]
    rng = random.Random(args.seed)
    pairs = meta["od_pairs"]
    paths: dict[tuple[str, str], list[str]] = {}
    for origin, destination in pairs:
        route, length = net.getShortestPath(anchors[origin], anchors[destination], vClass="passenger")
        if route is None:
            raise RuntimeError(f"No passenger path {origin} -> {destination}")
        # Check every archetype against every edge before generating any vehicles.
        for vtype, vclass in (("two_wheeler", "motorcycle"), ("car", "passenger"),
                              ("auto_rickshaw", "passenger"), ("bus", "bus"), ("truck", "truck")):
            denied = [edge.getID() for edge in route if not edge.allows(vclass)]
            if denied:
                raise RuntimeError(f"{vtype} route {origin}->{destination} has {len(denied)} inaccessible edges; first={denied[0]}")
        paths[(origin, destination)] = [edge.getID() for edge in route]
    total = max(1, round(demand * args.duration / 3600))
    types = list(shares)
    weights = [shares[x] for x in types]
    rows = []
    for i in range(total):
        pair = pairs[i % len(pairs)]
        vtype = rng.choices(types, weights=weights, k=1)[0]
        depart = rng.uniform(0, args.duration - 1)
        rows.append((depart, i, vtype, pair))
    rows.sort()
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<routes>',
             '    <!-- Generated synthetic demand; rates/shares are scenario assumptions. -->']
    route_ids = {}
    for ix, pair in enumerate(pairs):
        rid = f"od_{pair[0]}_{pair[1]}"
        route_ids[tuple(pair)] = rid
        lines.append(f'    <route id="{rid}" edges="{" ".join(paths[tuple(pair)])}"/>')
    for depart, i, vtype, pair in rows:
        lines.append(f'    <vehicle id="veh_{args.seed}_{i:05d}" type="{vtype}" route="{route_ids[tuple(pair)]}" depart="{depart:.2f}" departLane="best" departSpeed="desired"/>')
    lines.append('</routes>')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"scenario": args.scenario, "seed": args.seed, "duration_s": args.duration,
                      "assumed_vehicles_per_hour": demand, "vehicles": total,
                      "composition_profile": args.composition_profile, "vehicle_shares_assumed": shares,
                      "route_edge_counts": {f"{a}->{b}": len(paths[(a,b)]) for a,b in pairs},
                      "vehicle_types": VEH_TYPES, "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
