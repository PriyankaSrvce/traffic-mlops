"""Lane queue definitions shared by collection, controllers and unit tests."""
from __future__ import annotations
from typing import Iterable

HALT_SPEED_MPS = 0.1
MAX_QUEUE_GAP_M = 2.5
PROXY_METERS_PER_HALTING_VEHICLE = 5.0


def measure_lane_queue(vehicles: Iterable[dict], *, halt_speed_mps: float = HALT_SPEED_MPS,
                       max_gap_m: float = MAX_QUEUE_GAP_M) -> dict[str, float | int]:
    """Return the downstream contiguous stopped queue.

    Each input has lanePosition (front position in metres), length (metres),
    and speed (m/s). Starting at the downstream-most stopped vehicle, include
    upstream stopped vehicles while their bumper gap is at most max_gap_m.
    Length spans the leading front bumper to the tail rear bumper, including
    gaps. The 5 m-per-halting-vehicle legacy proxy is returned separately.
    """
    records = [v for v in vehicles if float(v["speed"]) <= halt_speed_mps]
    records.sort(key=lambda v: float(v["lanePosition"]), reverse=True)
    if not records:
        return {"queue_length_m": 0.0, "queue_vehicle_count": 0,
                "halting_vehicle_count": 0, "queue_proxy_5m": 0.0}
    downstream_front = float(records[0]["lanePosition"])
    tail_rear = downstream_front - float(records[0]["length"])
    queue_count = 1
    for vehicle in records[1:]:
        front = float(vehicle["lanePosition"])
        rear = front - float(vehicle["length"])
        gap = tail_rear - front
        if gap < -0.05:
            # SUMO positions are fronts; overlapping records are conservatively
            # treated as a connected queue with no negative physical gap.
            gap = 0.0
        if gap > max_gap_m:
            break
        tail_rear = rear
        queue_count += 1
    length = max(0.0, downstream_front - tail_rear)
    return {"queue_length_m": round(length, 3), "queue_vehicle_count": queue_count,
            "halting_vehicle_count": len(records),
            "queue_proxy_5m": round(len(records) * PROXY_METERS_PER_HALTING_VEHICLE, 2)}
