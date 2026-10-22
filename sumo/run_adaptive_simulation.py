import csv
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import traci

ROOT = Path(__file__).resolve().parent.parent
SUMO_DIR = ROOT / "sumo"
NET_FILE = SUMO_DIR / "grid_network_tls.net.xml"
ROUTE_FILE = SUMO_DIR / "traffic.rou.xml"

REPORT_DIR = ROOT / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

SEED = int(os.environ.get("SUMO_SEED", "42"))
SIMULATION_END_S = 2100
GREEN_PHASES = {0, 2}
MIN_GREEN_S = 20
MAX_GREEN_S = 60
GREEN_BASE_S = 20
SECONDS_PER_HALTING_VEHICLE = 2

DECISIONS_FILE = REPORT_DIR / "adaptive_control_decisions.csv"
TRIPINFO_FILE = REPORT_DIR / "adaptive_tripinfo.xml"
SUMMARY_FILE = REPORT_DIR / "adaptive_summary.xml"

TLS_IDS = ["B1", "B2", "C1", "C2"]


def main():
    for file_path in [NET_FILE, ROUTE_FILE]:
        if not file_path.exists():
            raise FileNotFoundError(f"Required file not found: {file_path}")

    sumo_binary = os.environ.get("SUMO_BINARY", "sumo")

    command = [
        sumo_binary,
        "-n", str(NET_FILE),
        "-r", str(ROUTE_FILE),
        "--begin", "0",
        "--end", str(SIMULATION_END_S),
        "--seed", str(SEED),
        "--no-step-log", "true",
        "--tripinfo-output", str(TRIPINFO_FILE),
        "--summary-output", str(SUMMARY_FILE),
    ]

    print("Starting adaptive traffic simulation...")
    print("Random seed:", SEED)
    print("Network:", NET_FILE.name)
    print("Routes:", ROUTE_FILE.name)

    traci.start(command)

    decisions = []
    green_extensions = 0

    try:
        # Preserve the original 42-second duration for each initial
        # green phase. Adapt subsequent green phases using observed queues.
        last_phase = {
            tls_id: traci.trafficlight.getPhase(tls_id)
            for tls_id in TLS_IDS
        }

        while traci.simulation.getMinExpectedNumber() > 0:
            sim_time = traci.simulation.getTime()

            if sim_time >= SIMULATION_END_S:
                break

            for tls_id in TLS_IDS:
                phase_id = traci.trafficlight.getPhase(tls_id)

                # Make a decision only once when a new green phase begins.
                if phase_id in GREEN_PHASES and phase_id != last_phase[tls_id]:
                    signal_state = traci.trafficlight.getRedYellowGreenState(
                        tls_id
                    )
                    controlled_links = traci.trafficlight.getControlledLinks(
                        tls_id
                    )

                    # Identify unique incoming lanes served by green links.
                    green_lanes = set()

                    for index, signal in enumerate(signal_state):
                        if signal not in ("G", "g"):
                            continue

                        if index >= len(controlled_links):
                            continue

                        for link in controlled_links[index]:
                            if link and link[0]:
                                green_lanes.add(link[0])

                    halting_count = sum(
                        traci.lane.getLastStepHaltingNumber(lane_id)
                        for lane_id in green_lanes
                    )

                    green_duration = min(
                        MAX_GREEN_S,
                        max(
                            MIN_GREEN_S,
                            GREEN_BASE_S
                            + SECONDS_PER_HALTING_VEHICLE * halting_count,
                        ),
                    )

                    # Change only the remaining duration of this green phase.
                    # Existing phase order and yellow phases remain unchanged.
                    traci.trafficlight.setPhaseDuration(
                        tls_id, float(green_duration)
                    )

                    decisions.append({
                        "simulation_time_s": round(sim_time, 1),
                        "intersection_id": tls_id,
                        "phase_id": phase_id,
                        "green_lane_count": len(green_lanes),
                        "halting_vehicle_count": halting_count,
                        "selected_green_duration_s": green_duration,
                    })

                    green_extensions += 1

                    print(
                        f"t={sim_time:6.1f}s | {tls_id} | "
                        f"phase={phase_id} | "
                        f"halting={halting_count} | "
                        f"green={green_duration}s"
                    )

                last_phase[tls_id] = phase_id

            traci.simulationStep()

    finally:
        traci.close()

    with DECISIONS_FILE.open(
        "w", newline="", encoding="utf-8"
    ) as csv_file:
        fieldnames = [
            "simulation_time_s",
            "intersection_id",
            "phase_id",
            "green_lane_count",
            "halting_vehicle_count",
            "selected_green_duration_s",
        ]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(decisions)

    print("\nAdaptive simulation finished.")
    print("Green-phase decisions:", green_extensions)
    print("Decision log:", DECISIONS_FILE)
    print("Trip information:", TRIPINFO_FILE)
    print("Simulation summary:", SUMMARY_FILE)

    if TRIPINFO_FILE.exists():
        root = ET.parse(TRIPINFO_FILE).getroot()
        trips = root.findall("tripinfo")

        if trips:
            count = len(trips)
            avg_duration = sum(
                float(trip.get("duration", "0")) for trip in trips
            ) / count
            avg_waiting = sum(
                float(trip.get("waitingTime", "0")) for trip in trips
            ) / count
            avg_time_loss = sum(
                float(trip.get("timeLoss", "0")) for trip in trips
            ) / count
            avg_route_length = sum(
                float(trip.get("routeLength", "0")) for trip in trips
            ) / count

            print("\nCompleted-trip metrics:")
            print("Completed trips:", count)
            print(f"Average trip duration: {avg_duration:.2f} s")
            print(f"Average waiting time: {avg_waiting:.2f} s")
            print(f"Average time loss: {avg_time_loss:.2f} s")
            print(f"Average route length: {avg_route_length:.2f} m")
        else:
            print("No completed trips were found in the trip information.")


if __name__ == "__main__":
    main()
