"""Replay labelled SUMO observations against the running API as simulated production traffic.

Phase 3 live-monitoring demo. Each row of a labelled batch is sent to POST /api/v1/predict;
the true queue 60 s later (already known in the simulation) is then sent to
POST /api/v1/feedback, standing in for ground truth that would arrive after the horizon.
Prometheus scrapes the API and Grafana shows the request rate, latency, input/prediction
distributions and the live error of the model and of the persistence baseline.

Phases are replayed in order, so a dashboard viewer can watch normal traffic, then a demand
surge, then a faulty speed sensor.

Uses only the Python standard library. Rows are sampled with a fixed seed.

Usage:
  python scripts/replay_production_traffic.py --base-url http://localhost:8000 \
      --phase normal=test.csv --phase surge=surge_720.csv --phase sensor_fault=fault.csv \
      --rows-per-phase 600 --occupied-only
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import random
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

LOGGER = logging.getLogger("replay")
TARGET = "queue_length_m_t_plus_60s"
TEXT_FIELDS = ["intersection_id", "approach_id", "lane_id", "signal_phase_id", "signal_state", "vehicle_composition"]


def to_request(row: dict) -> dict:
    payload = {"queue_length_m": float(row["queue_length_m"]), "vehicle_count": int(float(row["vehicle_count"])),
               "halting_vehicle_count": int(float(row["halting_vehicle_count"])),
               "mean_speed_mps": float(row["mean_speed_mps"]), "phase_elapsed_s": float(row["phase_elapsed_s"])}
    payload.update({name: str(row[name]) for name in TEXT_FIELDS})
    return payload


def post(url: str, payload: dict, timeout: float) -> dict:
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def replay_row(base_url: str, row: dict, timeout: float) -> tuple[float, float] | None:
    try:
        payload = to_request(row)
        predicted = post(f"{base_url}/api/v1/predict", payload, timeout)["predicted_queue_length_m"]
        actual = float(row[TARGET])
        post(f"{base_url}/api/v1/feedback", {"lane_id": payload["lane_id"], "predicted_queue_length_m": predicted,
                                             "actual_queue_length_m": actual,
                                             "queue_length_m_at_prediction": payload["queue_length_m"]}, timeout)
        return abs(predicted - actual), abs(payload["queue_length_m"] - actual)
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as exc:
        LOGGER.warning("request_failed reason=%s", exc)
        return None


def load_rows(path: str, occupied_only: bool, count: int, seed: int) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if not occupied_only or float(r["vehicle_count"]) > 0]
    random.Random(seed).shuffle(rows)
    return rows[:count]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--phase", action="append", required=True, help="NAME=labelled.csv (repeatable, replayed in order)")
    ap.add_argument("--rows-per-phase", type=int, default=600)
    ap.add_argument("--occupied-only", action="store_true", help="replay only lanes with vehicles (vehicle_count > 0)")
    ap.add_argument("--min-phase-seconds", type=float, default=90, help="pad each phase so it is visible on the dashboard")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=60)
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    for spec in a.phase:
        name, _, path = spec.partition("=")
        rows = load_rows(path, a.occupied_only, a.rows_per_phase, a.seed)
        start, results = time.perf_counter(), []
        delay = a.min_phase_seconds / max(len(rows), 1)
        LOGGER.info("phase_start name=%s rows=%d occupied_only=%s", name, len(rows), a.occupied_only)
        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            futures = []
            for index, row in enumerate(rows):
                futures.append(pool.submit(replay_row, a.base_url, row, a.timeout))
                pause = start + (index + 1) * delay - time.perf_counter()
                if pause > 0:
                    time.sleep(pause)
            results = [f.result() for f in futures]
        ok = [r for r in results if r]
        if ok:
            LOGGER.info("phase_done name=%s sent=%d failed=%d seconds=%.0f model_mae_m=%.4f persistence_mae_m=%.4f",
                        name, len(ok), len(results) - len(ok), time.perf_counter() - start,
                        sum(r[0] for r in ok) / len(ok), sum(r[1] for r in ok) / len(ok))
        else:
            LOGGER.error("phase_done name=%s sent=0 failed=%d", name, len(results))


if __name__ == "__main__":
    main()
