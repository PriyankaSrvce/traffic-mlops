import csv
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import joblib
import pandas as pd
import traci

ROOT = Path(__file__).resolve().parent.parent
SUMO_DIR = ROOT / "sumo"
NET_FILE = SUMO_DIR / "grid_network_tls.net.xml"
ROUTE_FILE = SUMO_DIR / "traffic.rou.xml"
MODEL_FILE = ROOT / "models" / "sumo_queue_rf_60s.joblib"

REPORT_DIR = ROOT / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

SEED = int(os.environ.get("SUMO_SEED", "42"))
SIMULATION_END_S = 2100

TLS_IDS = ["B1", "B2", "C1", "C2"]
GREEN_PHASES = {0, 2}

MIN_GREEN_S = 20
MAX_GREEN_S = 60
GREEN_BASE_S = 20
SECONDS_PER_EQUIVALENT_VEHICLE = 2.0

# Approximate occupied road length per queued vehicle.
# This is a heuristic, not a learned parameter.
METRES_PER_QUEUED_VEHICLE = 7.5

STOPPED_SPEED_MPS = 0.1
MAX_QUEUE_GAP_M = 2.5

TRIPINFO_FILE = REPORT_DIR / f"predictive60s_seed{SEED}_tripinfo.xml"
SUMMARY_FILE = REPORT_DIR / f"predictive60s_seed{SEED}_summary.xml"
DECISIONS_FILE = REPORT_DIR / f"predictive60s_seed{SEED}_decisions.csv"
PREDICTIONS_FILE = REPORT_DIR / f"predictive60s_seed{SEED}_predictions.csv"

FEATURES = [
    "queue_length_m",
    "vehicle_count",
    "halting_vehicle_count",
    "mean_speed_mps",
    "phase_elapsed_s",
    "intersection_id",
    "approach_id",
    "lane_id",
    "signal_phase_id",
    "signal_state",
]


def get_queue_length(lane_id):
    """Use the same queue definition as the training-data collector."""
    lane_length = traci.lane.getLength(lane_id)
    vehicle_ids = traci.lane.getLastStepVehicleIDs(lane_id)
    stopped = []

    for vehicle_id in vehicle_ids:
        speed = traci.vehicle.getSpeed(vehicle_id)

        if speed <= STOPPED_SPEED_MPS:
            front_position = traci.vehicle.getLanePosition(vehicle_id)
            vehicle_length = traci.vehicle.getLength(vehicle_id)
            rear_position = max(0.0, front_position - vehicle_length)
            stopped.append((front_position, rear_position))

    if not stopped:
        return 0.0, len(vehicle_ids), 0

    stopped.sort(key=lambda item: item[0], reverse=True)

    queue_rear = stopped[0][1]

    for front, rear in stopped[1:]:
        gap = queue_rear - front

        if gap <= MAX_QUEUE_GAP_M:
            queue_rear = min(queue_rear, rear)
        else:
            break

    queue_length = min(
        lane_length,
        max(0.0, lane_length - queue_rear),
    )

    return queue_length, len(vehicle_ids), len(stopped)


def observe_lane(lane_id, tls_id):
    """Construct the exact feature schema expected by the saved model."""
    vehicle_ids = traci.lane.getLastStepVehicleIDs(lane_id)
    vehicle_count = len(vehicle_ids)

    if vehicle_count:
        mean_speed = sum(
            traci.vehicle.getSpeed(vehicle_id)
            for vehicle_id in vehicle_ids
        ) / vehicle_count
    else:
        mean_speed = 0.0

    queue_length, _, halting_count = get_queue_length(lane_id)

    signal_phase_id = traci.trafficlight.getPhase(tls_id)
    signal_state = traci.trafficlight.getRedYellowGreenState(tls_id)
    phase_elapsed = traci.trafficlight.getSpentDuration(tls_id)

    return {
        "queue_length_m": round(queue_length, 3),
        "vehicle_count": vehicle_count,
        "halting_vehicle_count": halting_count,
        "mean_speed_mps": round(mean_speed, 3),
        "phase_elapsed_s": round(phase_elapsed, 3),
        "intersection_id": tls_id,
        "approach_id": lane_id.rsplit("_", 1)[0],
        "lane_id": lane_id,
        "signal_phase_id": signal_phase_id,
        "signal_state": signal_state,
    }


def get_green_lanes(tls_id):
    """Find unique incoming lanes served by the active green phase."""
    state = traci.trafficlight.getRedYellowGreenState(tls_id)
    controlled_links = traci.trafficlight.getControlledLinks(tls_id)
    lanes = set()

    for index, signal in enumerate(state):
        if signal not in ("G", "g"):
            continue

        if index >= len(controlled_links):
            continue

        for link in controlled_links[index]:
            if link and link[0]:
                lanes.add(link[0])

    return lanes


def main():
    for path in [NET_FILE, ROUTE_FILE, MODEL_FILE]:
        if not path.exists():
            raise FileNotFoundError(f"Required file not found: {path}")

    model = joblib.load(MODEL_FILE)

    model_features = list(model.feature_names_in_)
    if model_features != FEATURES:
        raise ValueError(
            "Saved model feature schema differs from the expected schema.\n"
            f"Expected: {FEATURES}\n"
            f"Found:    {model_features}"
        )

    command = [
        os.environ.get("SUMO_BINARY", "sumo"),
        "-n", str(NET_FILE),
        "-r", str(ROUTE_FILE),
        "--begin", "0",
        "--end", str(SIMULATION_END_S),
        "--seed", str(SEED),
        "--no-step-log", "true",
        "--tripinfo-output", str(TRIPINFO_FILE),
        "--summary-output", str(SUMMARY_FILE),
    ]

    print("Starting prediction-driven traffic simulation")
    print("Seed:", SEED)
    print("Model:", MODEL_FILE.name)
    print("Prediction horizon: 60 seconds")
    print("Green duration limits:", MIN_GREEN_S, "to", MAX_GREEN_S)

    decisions = []
    predictions_log = []

    traci.start(command)

    try:
        lane_to_tls = {}

        for tls_id in TLS_IDS:
            controlled_links = traci.trafficlight.getControlledLinks(tls_id)

            for link_group in controlled_links:
                for link in link_group:
                    if link and link[0]:
                        lane_to_tls.setdefault(link[0], set()).add(tls_id)

        last_phase = {
            tls_id: traci.trafficlight.getPhase(tls_id)
            for tls_id in TLS_IDS
        }

        print("Unique incoming lanes discovered:", len(lane_to_tls))

        while traci.simulation.getMinExpectedNumber() > 0:
            sim_time = traci.simulation.getTime()

            if sim_time >= SIMULATION_END_S:
                break

            for tls_id in TLS_IDS:
                phase_id = traci.trafficlight.getPhase(tls_id)

                # Make one decision when a new green phase begins.
                if phase_id in GREEN_PHASES and phase_id != last_phase[tls_id]:
                    green_lanes = get_green_lanes(tls_id)

                    # Predict the future queue on every incoming lane
                    # associated with this intersection.
                    intersection_lanes = sorted(
                        lane_id
                        for lane_id, tls_set in lane_to_tls.items()
                        if tls_id in tls_set
                    )

                    lane_predictions = {}

                    if intersection_lanes:
                        feature_rows = [
                            observe_lane(lane_id, tls_id)
                            for lane_id in intersection_lanes
                        ]

                        feature_frame = pd.DataFrame(
                            feature_rows,
                            columns=FEATURES,
                        )

                        
                        categorical_features = [
                            "intersection_id",
                            "approach_id",
                            "lane_id",
                            "signal_phase_id",
                            "signal_state",
                        ]

                        for column in categorical_features:
                            feature_frame[column] = feature_frame[column].astype(str)

                        predicted_queues = model.predict(feature_frame)


                        for lane_id, features, prediction in zip(
                            intersection_lanes,
                            feature_rows,
                            predicted_queues,
                        ):
                            predicted_queue = max(0.0, float(prediction))
                            lane_predictions[lane_id] = predicted_queue

                            predictions_log.append({
                                "simulation_time_s": round(sim_time, 1),
                                "intersection_id": tls_id,
                                "lane_id": lane_id,
                                "observed_queue_length_m":
                                    features["queue_length_m"],
                                "predicted_queue_length_m_t_plus_60s":
                                    round(predicted_queue, 3),
                            })

                    # Only the lanes served by the currently active
                    # green phase contribute to this phase's demand.
                    predicted_green_queue_m = sum(
                        lane_predictions.get(lane_id, 0.0)
                        for lane_id in green_lanes
                    )

                    equivalent_vehicles = (
                        predicted_green_queue_m
                        / METRES_PER_QUEUED_VEHICLE
                    )

                    green_duration = min(
                        MAX_GREEN_S,
                        max(
                            MIN_GREEN_S,
                            round(
                                GREEN_BASE_S
                                + SECONDS_PER_EQUIVALENT_VEHICLE
                                * equivalent_vehicles
                            ),
                        ),
                    )

                    traci.trafficlight.setPhaseDuration(
                        tls_id, float(green_duration)
                    )

                    decisions.append({
                        "simulation_time_s": round(sim_time, 1),
                        "intersection_id": tls_id,
                        "phase_id": phase_id,
                        "green_lane_count": len(green_lanes),
                        "predicted_green_queue_m":
                            round(predicted_green_queue_m, 3),
                        "predicted_equivalent_vehicles":
                            round(equivalent_vehicles, 3),
                        "selected_green_duration_s": green_duration,
                    })

                    print(
                        f"t={sim_time:6.1f}s | {tls_id} | "
                        f"phase={phase_id} | "
                        f"predicted_queue={predicted_green_queue_m:.1f}m | "
                        f"green={green_duration}s"
                    )

                last_phase[tls_id] = phase_id

            traci.simulationStep()

    finally:
        traci.close()

    with DECISIONS_FILE.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        fields = [
            "simulation_time_s",
            "intersection_id",
            "phase_id",
            "green_lane_count",
            "predicted_green_queue_m",
            "predicted_equivalent_vehicles",
            "selected_green_duration_s",
        ]
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(decisions)

    with PREDICTIONS_FILE.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        fields = [
            "simulation_time_s",
            "intersection_id",
            "lane_id",
            "observed_queue_length_m",
            "predicted_queue_length_m_t_plus_60s",
        ]
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(predictions_log)

    print("\nPrediction-driven simulation finished.")
    print("Control decisions:", len(decisions))
    print("Lane predictions:", len(predictions_log))
    print("Decision log:", DECISIONS_FILE)
    print("Prediction log:", PREDICTIONS_FILE)
    print("Trip information:", TRIPINFO_FILE)
    print("Simulation summary:", SUMMARY_FILE)

    if TRIPINFO_FILE.exists():
        trips = ET.parse(TRIPINFO_FILE).getroot().findall("tripinfo")

        if trips:
            count = len(trips)
            print("Completed trips:", count)

            for field, label in [
                ("duration", "Average trip duration"),
                ("waitingTime", "Average waiting time"),
                ("timeLoss", "Average time loss"),
                ("routeLength", "Average route length"),
            ]:
                average = sum(
                    float(trip.get(field, "0"))
                    for trip in trips
                ) / count
                print(f"{label}: {average:.2f} s" if field != "routeLength"
                      else f"{label}: {average:.2f} m")


if __name__ == "__main__":
    main()

