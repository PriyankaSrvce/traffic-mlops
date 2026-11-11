import csv
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import traci

ROOT = Path(__file__).resolve().parent.parent
NET_FILE = ROOT / "sumo" / "grid_network_tls.net.xml"
ROUTE_FILE = Path(os.environ.get(
    "SUMO_ROUTE_FILE", str(ROOT / "sumo" / "traffic.rou.xml")
)).resolve()
OUTPUT_FILE = Path(os.environ.get("SUMO_OUTPUT_FILE", str(ROOT / "data" / "processed" / "sumo_queue_observations.csv")))

TLS_IDS = ["B1", "B2", "C1", "C2"]
SAMPLE_INTERVAL_S = 5
SIMULATION_END_S = 2100
STOPPED_SPEED_MPS = 0.1
MAX_QUEUE_GAP_M = 2.5
RUN_ID = os.environ.get("SUMO_RUN_ID", "grid_seed42_v1")

FIELDS = [
    "run_id",
    "simulation_time_s",
    "intersection_id",
    "approach_id",
    "lane_id",
    "queue_length_m",
    "vehicle_count",
    "halting_vehicle_count",
    "mean_speed_mps",
    "signal_phase_id",
    "signal_state",
    "phase_elapsed_s",
]


def get_queue_length(lane_id):
    """Estimate the contiguous stopped queue nearest the stop line."""
    lane_length = traci.lane.getLength(lane_id)
    vehicles = traci.lane.getLastStepVehicleIDs(lane_id)
    stopped = []

    for vehicle_id in vehicles:
        speed = traci.vehicle.getSpeed(vehicle_id)
        if speed <= STOPPED_SPEED_MPS:
            front_position = traci.vehicle.getLanePosition(vehicle_id)
            vehicle_length = traci.vehicle.getLength(vehicle_id)
            rear_position = max(0.0, front_position - vehicle_length)
            stopped.append((front_position, rear_position))

    if not stopped:
        return 0.0, len(vehicles), 0

    # Sort from the vehicle nearest the stop line to the upstream end.
    stopped.sort(key=lambda item: item[0], reverse=True)

    queue_front = stopped[0][0]
    queue_rear = stopped[0][1]

    for front, rear in stopped[1:]:
        gap = queue_rear - front
        if gap <= MAX_QUEUE_GAP_M:
            queue_rear = min(queue_rear, rear)
        else:
            break

    queue_length = min(lane_length, max(0.0, lane_length - queue_rear))
    return queue_length, len(vehicles), len(stopped)


def main():
    if not NET_FILE.exists():
        raise FileNotFoundError(f"Network not found: {NET_FILE}")
    if not ROUTE_FILE.exists():
        raise FileNotFoundError(f"Routes not found: {ROUTE_FILE}")

    if OUTPUT_FILE.exists():
        raise FileExistsError(f"Refusing to overwrite existing observations: {OUTPUT_FILE}")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    sumo_binary = os.environ.get("SUMO_BINARY", "sumo")
    command = [
        sumo_binary,
        "-n", str(NET_FILE),
        "-r", str(ROUTE_FILE),
        "--begin", "0",
        "--end", str(SIMULATION_END_S),
        "--seed", os.environ.get("SUMO_SEED", "42"),
        "--no-step-log", "true",
    ]

    traci.start(command)

    try:
        # Obtain incoming lanes from the actual controlled signal links.
        lane_to_tls = {}
        for tls_id in TLS_IDS:
            controlled_links = traci.trafficlight.getControlledLinks(tls_id)
            for link_group in controlled_links:
                for link in link_group:
                    if link and link[0]:
                        lane_to_tls.setdefault(link[0], set()).add(tls_id)

        # A lane may have multiple connections to the same intersection.
        lane_to_tls = {
            lane: tls_set
            for lane, tls_set in lane_to_tls.items()
            if tls_set
        }

        if not lane_to_tls:
            raise RuntimeError("No incoming lanes found for the requested signals.")

        print("Incoming lanes discovered:", len(lane_to_tls))
        for tls_id in TLS_IDS:
            lanes = sorted(
                lane for lane, tls_set in lane_to_tls.items()
                if tls_id in tls_set
            )
            print(f"{tls_id}: {len(lanes)} unique incoming lanes")

        with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=FIELDS)
            writer.writeheader()

            next_sample = 0
            while traci.simulation.getMinExpectedNumber() > 0:
                sim_time = int(round(traci.simulation.getTime()))

                if sim_time >= SIMULATION_END_S:
                    break

                if sim_time >= next_sample:
                    for lane_id, tls_set in sorted(lane_to_tls.items()):
                        vehicle_ids = traci.lane.getLastStepVehicleIDs(lane_id)
                        vehicle_count = len(vehicle_ids)

                        if vehicle_count:
                            mean_speed = sum(
                                traci.vehicle.getSpeed(v)
                                for v in vehicle_ids
                            ) / vehicle_count
                        else:
                            mean_speed = 0.0

                        queue_length, _, halting_count = get_queue_length(lane_id)

                        for tls_id in sorted(tls_set):
                            phase_id = traci.trafficlight.getPhase(tls_id)
                            signal_state = traci.trafficlight.getRedYellowGreenState(tls_id)
                            phase_elapsed = traci.trafficlight.getSpentDuration(tls_id)

                            writer.writerow({
                                "run_id": RUN_ID,
                                "simulation_time_s": sim_time,
                                "intersection_id": tls_id,
                                "approach_id": lane_id.rsplit("_", 1)[0],
                                "lane_id": lane_id,
                                "queue_length_m": round(queue_length, 3),
                                "vehicle_count": vehicle_count,
                                "halting_vehicle_count": halting_count,
                                "mean_speed_mps": round(mean_speed, 3),
                                "signal_phase_id": phase_id,
                                "signal_state": signal_state,
                                "phase_elapsed_s": round(phase_elapsed, 3),
                            })

                    if sim_time % 60 == 0:
                        print(f"Collected observations at t={sim_time}s")

                    next_sample = sim_time + SAMPLE_INTERVAL_S

                traci.simulationStep()

    finally:
        traci.close()

    print(f"\nCollection finished: {OUTPUT_FILE}")
    print(f"CSV exists: {OUTPUT_FILE.exists()}")
    if OUTPUT_FILE.exists():
        with OUTPUT_FILE.open("r", encoding="utf-8") as csv_file:
            row_count = sum(1 for _ in csv_file) - 1
        print(f"Observation rows: {row_count}")


if __name__ == "__main__":
    main()

