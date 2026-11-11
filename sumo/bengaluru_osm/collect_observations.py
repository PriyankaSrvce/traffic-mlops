"""Collect approach-level observations from one Bengaluru SUMO run via TraCI."""
from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict
from pathlib import Path

import sumolib
from queue_measurement import measure_lane_queue

HERE = Path(__file__).resolve().parent
FIELDS = ["run_id", "seed", "scenario", "time_s", "intersection_id", "approach_id", "lane_id",
          "queue_length_m", "queue_vehicle_count", "queue_proxy_5m", "vehicle_count", "halting_vehicle_count", "mean_speed_mps",
          "waiting_time_s", "occupancy_pct", "vehicle_type_mix", "vehicle_composition", "signal_phase_id", "signal_state",
          "phase_elapsed_s"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=("low", "medium", "high"), default="low")
    ap.add_argument("--seed", type=int, default=21)
    ap.add_argument("--step", type=int, default=10)
    ap.add_argument("--duration", type=int, default=900)
    ap.add_argument("--output", type=Path, default=HERE / "observations.csv")
    ap.add_argument("--routes", type=Path, default=HERE / "traffic.rou.xml")
    ap.add_argument("--sumo", default="sumo")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--composition-profile", default="balanced_assumed")
    ap.add_argument("--tripinfo", type=Path, default=None)
    ap.add_argument("--statistics", type=Path, default=None)
    ap.add_argument("--collisions", type=Path, default=None)
    ap.add_argument("--time-to-teleport", type=int, default=300,
                    help="SUMO recovery timeout; teleports are recorded and can fail run quality.")
    ap.add_argument("--max-drain", type=int, default=3600)
    a = ap.parse_args()
    if not a.routes.exists():
        raise SystemExit("Generate traffic.rou.xml first with generate_scenario.py")
    net = sumolib.net.readNet(str(HERE / "bengaluru_osm_sim.net.xml"), withInternal=False)
    # Keep only TLS approaches appearing on an actual anchor-to-anchor route.
    relevant: dict[str, set[str]] = defaultdict(set)
    anchors = [net.getEdge(json_edge) for json_edge in ("1208112310#1", "-133945864", "558765859#3")]
    pairs = [(0, 1), (1, 0), (1, 2), (2, 1), (0, 2), (2, 0)]
    for i, j in pairs:
        route, _ = net.getShortestPath(anchors[i], anchors[j], vClass="passenger")
        for edge in route or []:
            for outgoing, conns in edge.getOutgoing().items():
                for conn in conns:
                    tls = conn.getTLSID()
                    if tls:
                        relevant[tls].add(conn.getFromLane().getID())
    sys.path.append(os.environ.get("SUMO_HOME", ""))
    import traci
    cfg = HERE / "demo.sumocfg"
    max_end = a.duration + a.max_drain
    cmd = [a.sumo, "-c", str(cfg), "--route-files", str(a.routes.resolve()), "--end", str(max_end),
           "--time-to-teleport", str(a.time_to_teleport), "--seed", str(a.seed), "--no-step-log", "true"]
    if a.tripinfo: cmd += ["--tripinfo-output", str(a.tripinfo.resolve())]
    if a.statistics: cmd += ["--statistic-output", str(a.statistics.resolve())]
    if a.collisions: cmd += ["--collision-output", str(a.collisions.resolve()), "--collision.check-junctions"]
    traci.start(cmd)
    run_id = a.run_id or f"bengaluru_{a.scenario}_seed{a.seed}"
    rows = []
    previous_phase: dict[str, tuple[int, float]] = {}
    try:
        while True:
            before = traci.simulation.getTime()
            if before >= max_end or (before >= a.duration and traci.simulation.getMinExpectedNumber() <= 0):
                break
            traci.simulationStep()
            now = traci.simulation.getTime()
            if now <= before:  # SUMO stopped advancing at its configured end.
                break
            if round(now) % a.step:
                continue
            for tls, lane_ids in relevant.items():
                if tls not in traci.trafficlight.getIDList():
                    continue
                phase = traci.trafficlight.getPhase(tls)
                if tls not in previous_phase or previous_phase[tls][0] != phase:
                    previous_phase[tls] = (phase, now)
                elapsed = now - previous_phase[tls][1]
                state = traci.trafficlight.getRedYellowGreenState(tls)
                for lane in lane_ids:
                    vids = traci.lane.getLastStepVehicleIDs(lane)
                    speeds = [traci.vehicle.getSpeed(v) for v in vids]
                    queue = measure_lane_queue([{"lanePosition": traci.vehicle.getLanePosition(v),
                                                "length": traci.vehicle.getLength(v),
                                                "speed": traci.vehicle.getSpeed(v)} for v in vids])
                    types: dict[str, int] = defaultdict(int)
                    for v in vids:
                        types[traci.vehicle.getTypeID(v)] += 1
                    rows.append({"run_id": run_id, "seed": a.seed, "scenario": a.scenario, "time_s": now,
                                 "intersection_id": tls, "approach_id": lane.rsplit("_", 1)[0], "lane_id": lane,
                                 "queue_length_m": queue["queue_length_m"],
                                 "queue_vehicle_count": queue["queue_vehicle_count"],
                                 "queue_proxy_5m": queue["queue_proxy_5m"],
                                 "vehicle_count": len(vids), "halting_vehicle_count": queue["halting_vehicle_count"],
                                 "mean_speed_mps": round(sum(speeds) / len(speeds), 4) if speeds else 0.0,
                                 "waiting_time_s": round(sum(traci.vehicle.getWaitingTime(v) for v in vids), 2),
                                 "occupancy_pct": traci.lane.getLastStepOccupancy(lane),
                                 "vehicle_type_mix": ";".join(f"{k}:{types[k]}" for k in sorted(types)),
                                 "vehicle_composition": a.composition_profile,
                                 "signal_phase_id": phase, "signal_state": state,
                                 "phase_elapsed_s": round(elapsed, 2)})
    finally:
        traci.close()
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    print(f"run={run_id} observations={len(rows)} tls={len(relevant)} output={a.output}")


if __name__ == "__main__":
    main()
