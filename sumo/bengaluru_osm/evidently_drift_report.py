"""Evidently drift and model-quality reports for simulated production batches.

Phase 3 monitoring. For each batch this builds an Evidently report with
  - DataDriftPreset   : per-feature drift tests (Evidently's default test per column type)
  - RegressionPreset  : MAE / RMSE / R2 of the served model on the batch vs the reference

Reference = the held-out test set the production model was approved on. Each batch is
checked on all rows and on occupied lanes (vehicle_count > 0), because ~97 % of rows are
empty lanes and dilute a demand shift (same segment rule as drift_detection.py).

Like-for-like rule: --composition keeps only rows of one assumed vehicle mix in the
reference and in every batch. The new batches were simulated with the balanced mix only,
while the full test set is about half motorcycle-heavy; without the filter Evidently
(correctly) reports that mix difference as drift, which would hide the effect under test.

Outputs: one HTML report per batch and segment, plus evidently_summary.json with every
drift score, so the dashboard and the written report quote Evidently's own numbers.

Runs in its own environment (requirements-monitoring.txt); Evidently is not needed to serve
the model.

Usage:
  python sumo/bengaluru_osm/evidently_drift_report.py \
      --reference test.csv,test_predictions.csv \
      --batch surge_600=surge_600.csv,surge_600_predictions.csv [--batch ...] \
      --output-dir reports/phase3_drift/evidently
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

LOGGER = logging.getLogger("evidently_drift")
KEYS = ["run_id", "seed", "scenario", "vehicle_composition", "intersection_id", "approach_id", "lane_id", "time_s"]
NUMERICAL = ["queue_length_m", "vehicle_count", "halting_vehicle_count", "mean_speed_mps", "phase_elapsed_s"]
CATEGORICAL = ["intersection_id", "signal_phase_id", "vehicle_composition"]
TARGET, PREDICTION = "queue_length_m_t_plus_60s", "prediction_m"
BUNDLE_NAME = "evidently_bundle.js"
SEGMENTS = {"all_rows": lambda f: f, "occupied_lanes": lambda f: f[f["vehicle_count"] > 0]}


def load(spec: str, composition: str | None = None) -> pd.DataFrame:
    """Join a labelled batch with the served model's predictions on the exact observation keys."""
    data_path, _, pred_path = spec.partition(",")
    data, preds = pd.read_csv(data_path), pd.read_csv(pred_path)
    if composition:
        data = data[data["vehicle_composition"] == composition]
        preds = preds[preds["vehicle_composition"] == composition]
        if data.empty:
            raise ValueError(f"No '{composition}' rows in {data_path}")
    # The sensor-fault batch renames the scenario, so join on the keys that identify an observation.
    join_keys = [k for k in KEYS if k != "scenario"]
    frame = data.merge(preds[join_keys + [PREDICTION]], on=join_keys, validate="one_to_one")
    if len(frame) != len(data):
        raise ValueError(f"Predictions do not cover every row of {data_path}")
    for col in CATEGORICAL:
        frame[col] = frame[col].astype(str)
    return frame[NUMERICAL + CATEGORICAL + [TARGET, PREDICTION]]


def run_report(reference: pd.DataFrame, current: pd.DataFrame):
    from evidently import DataDefinition, Dataset, Regression, Report
    from evidently.presets import DataDriftPreset, RegressionPreset

    definition = DataDefinition(numerical_columns=NUMERICAL, categorical_columns=CATEGORICAL,
                                regression=[Regression(target=TARGET, prediction=PREDICTION)])
    report = Report([DataDriftPreset(columns=NUMERICAL + CATEGORICAL), RegressionPreset()])
    return report.run(Dataset.from_pandas(current, data_definition=definition),
                      Dataset.from_pandas(reference, data_definition=definition))


def summarize(snapshot) -> dict:
    """Pull Evidently's own drift scores and regression metrics out of the snapshot."""
    columns, quality, drifted = {}, {}, None
    for metric in snapshot.dict()["metrics"]:
        name, value = str(metric.get("metric_id") or metric.get("metric_name")), metric.get("value")
        if match := re.match(r"ValueDrift\(column=([^,]+),method=([^,]+),threshold=([^)]+)\)", name):
            column, method, threshold = match.group(1), match.group(2), float(match.group(3))
            score = float(value)
            # p-value tests flag drift below the threshold; distance tests flag drift above it.
            is_drift = score < threshold if "p_value" in method else score >= threshold
            columns[column] = {"method": method, "threshold": threshold, "score": score, "drift_detected": bool(is_drift)}
        elif name.startswith("DriftedColumnsCount"):
            drifted = {"count": int(value["count"]), "share": float(value["share"])}
        elif name.startswith("MAE("):
            quality["mae_m"] = float(value["mean"])
        elif name.startswith("RMSE("):
            quality["rmse_m"] = float(value)
        elif name.startswith("R2Score("):
            quality["r2"] = float(value)
    return {"drifted_columns": drifted, "drifted_column_names": sorted(c for c, v in columns.items() if v["drift_detected"]),
            "columns": columns, "model_quality": quality}


def share_script_bundle(html: Path) -> None:
    """Move Evidently's large inline viewer script into one shared evidently_bundle.js.

    Every report embeds the same ~3.5 MB script. Storing it once keeps the repository and
    the Docker image small; the report content itself is not changed.
    """
    text = html.read_text(encoding="utf-8")
    blocks = list(re.finditer(r"<script>(.*?)</script>", text, flags=re.S))
    biggest = max(blocks, key=lambda m: len(m.group(1)))
    bundle = html.parent / BUNDLE_NAME
    if bundle.exists() and bundle.read_text(encoding="utf-8") != biggest.group(1):
        raise ValueError("Evidently viewer script differs between reports; refusing to share it")
    bundle.write_text(biggest.group(1), encoding="utf-8")
    html.write_text(text[:biggest.start()] + f'<script src="{BUNDLE_NAME}"></script>' + text[biggest.end():], encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--reference", required=True, help="data.csv,predictions.csv of the approved held-out test set")
    ap.add_argument("--batch", action="append", required=True, help="NAME=data.csv,predictions.csv (repeatable)")
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--html-segments", default="all_rows,occupied_lanes", help="segments to save as HTML")
    ap.add_argument("--composition", default=None, help="keep only this vehicle_composition everywhere (like-for-like)")
    ap.add_argument("--reference-label", default="approved held-out test set")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    import evidently

    a.output_dir.mkdir(parents=True, exist_ok=True)
    html_segments = set(a.html_segments.split(","))
    reference = load(a.reference, a.composition)
    summary = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "tool": f"evidently {evidently.__version__}",
               "reference": a.reference_label, "composition_filter": a.composition, "reference_rows": int(len(reference)),
               "numerical_columns": NUMERICAL, "categorical_columns": CATEGORICAL, "batches": {}}
    for spec in a.batch:
        name, _, paths = spec.partition("=")
        current = load(paths, a.composition)
        summary["batches"][name] = {"rows": int(len(current))}
        for segment, select in SEGMENTS.items():
            ref_seg, cur_seg = select(reference), select(current)
            snapshot = run_report(ref_seg, cur_seg)
            result = summarize(snapshot)
            result.update(reference_rows=int(len(ref_seg)), current_rows=int(len(cur_seg)))
            if segment in html_segments:
                html = a.output_dir / f"{name}_{segment}.html"
                snapshot.save_html(str(html))
                share_script_bundle(html)
                result["html"] = html.name
            summary["batches"][name][segment] = result
            LOGGER.info("batch=%s segment=%s rows=%d drifted=%s mae_m=%.4f", name, segment, len(cur_seg),
                        result["drifted_column_names"], result["model_quality"].get("mae_m", float("nan")))
    (a.output_dir / "evidently_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    LOGGER.info("summary=%s", a.output_dir / "evidently_summary.json")


if __name__ == "__main__":
    main()
