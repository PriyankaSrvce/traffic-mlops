"""Detect data drift and model (performance) drift on a new batch of SUMO observations.

Phase 3. Compares a "production" batch against the training reference using the
project's own monitoring.run_monitor (PSI per feature, unknown categories, error
metrics), then applies an alert policy:

  DATA DRIFT          any monitored feature PSI >= 0.25  -> ALERT   (0.10-0.25 -> WATCH)
                      PSI is computed on all rows AND on occupied lanes (vehicle_count > 0):
                      ~97 % of rows are empty lanes, which dilutes a demand shift in the
                      all-rows PSI, so the occupied-lane segment is monitored as well.
  PERFORMANCE DRIFT   batch MAE more than 25 % worse than the approved model's test MAE,
                      or the model no longer beats persistence by the 5 % quality-gate margin
  ACTION              performance ALERT -> "retraining recommended" (run the Metaflow flow on
                      refreshed data; promotion still requires the quality gate)
                      data ALERT only   -> "investigate data pipeline" (do not retrain on
                      possibly corrupted inputs)
                      data WATCH only   -> "monitor closely"
  SCHEMA              > 1 % of rows with a category unseen in training -> data ALERT

The model is loaded only after its SHA-256 matches the approved metadata.

Usage:
  python sumo/bengaluru_osm/drift_detection.py --batch NAME=path/to/labeled.csv [--batch ...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from monitoring import KEYS, TARGET, metric_set, psi as psi_score, run_monitor  # noqa: E402
from bengaluru_model import HurdleQueueModel  # noqa: E402,F401  (needed to unpickle the model)

FEATURES = ["queue_length_m", "vehicle_count", "halting_vehicle_count", "mean_speed_mps", "phase_elapsed_s",
            "intersection_id", "approach_id", "lane_id", "signal_phase_id", "signal_state", "vehicle_composition"]
NUMERIC_IN = FEATURES[:5]
PSI_WATCH, PSI_ALERT = 0.10, 0.25
MAE_DEGRADATION_ALERT = 0.25      # 25 % worse than the approved test MAE
GATE_MARGIN = 0.95                # model MAE must stay <= 95 % of persistence MAE
UNKNOWN_CATEGORY_ALERT = 0.01     # > 1 % of rows with a category never seen in training


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_verified_model(model_path: Path, metadata_path: Path):
    meta = json.loads(metadata_path.read_text(encoding="utf-8"))
    digest = sha256(model_path)
    if meta.get("validation_status") != "passed" or digest != meta.get("sha256"):
        raise SystemExit(f"Refusing to load model: SHA-256 {digest[:12]} does not match approved metadata")
    return joblib.load(model_path), meta, digest


def predict_batch(model, frame: pd.DataFrame) -> pd.DataFrame:
    x = frame.copy()
    for col in NUMERIC_IN + [TARGET]:
        x[col] = pd.to_numeric(x[col])
    for col in FEATURES[5:]:
        x[col] = x[col].astype(str)
    out = frame[KEYS].copy()
    out[TARGET] = x[TARGET].to_numpy()
    out["prediction_m"] = model.predict(x[FEATURES])
    out["persistence_m"] = x["queue_length_m"].to_numpy()
    return out


def occupied_lane_psi(reference: pd.DataFrame, batch: pd.DataFrame) -> dict:
    ref = reference[pd.to_numeric(reference["vehicle_count"]) > 0]
    cur = batch[pd.to_numeric(batch["vehicle_count"]) > 0]
    out = {}
    for f in NUMERIC_IN + [TARGET]:
        score = psi_score(pd.to_numeric(ref[f]), pd.to_numeric(cur[f]))
        if score is not None:
            out[f"{f} [occupied lanes]"] = score
    return out


def assess(name: str, batch: pd.DataFrame, preds: pd.DataFrame, monitor: dict, approved_test_mae: float,
           reference: pd.DataFrame | None = None) -> dict:
    psi = {f: v["psi"] for f, v in monitor["feature_drift"].items() if v["psi"] is not None}
    if reference is not None:
        psi.update(occupied_lane_psi(reference, batch))
    worst_feature = max(psi, key=psi.get)
    persistence = metric_set(preds[TARGET], preds["persistence_m"])
    model = monitor["prediction_error"]
    degradation = model["mae_m"] / approved_test_mae - 1
    data_level = "ALERT" if psi[worst_feature] >= PSI_ALERT else "WATCH" if psi[worst_feature] >= PSI_WATCH else "OK"
    unknown = {f: v["unknown_rate"] for f, v in monitor["categorical_coverage"].items() if v["unknown_rate"] > UNKNOWN_CATEGORY_ALERT}
    beats_baseline = model["mae_m"] <= GATE_MARGIN * persistence["mae_m"]
    perf_level = "ALERT" if (degradation > MAE_DEGRADATION_ALERT or not beats_baseline) else "OK"
    alerts = []
    if data_level != "OK":
        alerts.append(f"DATA DRIFT {data_level}: '{worst_feature}' PSI={psi[worst_feature]:.3f}"
                      f" (watch >= {PSI_WATCH}, alert >= {PSI_ALERT})")
    if unknown:
        data_level = "ALERT"
        alerts.append(f"SCHEMA ALERT: unseen categories above {UNKNOWN_CATEGORY_ALERT:.0%}: "
                      + ", ".join(f"{f}={r:.1%}" for f, r in unknown.items()))
    if perf_level == "ALERT":
        alerts.append(f"PERFORMANCE DRIFT ALERT: MAE {model['mae_m']:.4f} m is {degradation:+.0%} vs approved "
                      f"{approved_test_mae:.4f} m; beats persistence by 5 %: {beats_baseline}")
    if perf_level == "ALERT":
        action = "RETRAINING RECOMMENDED"
    elif data_level == "ALERT":
        # Inputs shifted sharply but accuracy held: suspect the data pipeline (sensor, units,
        # schema) first. Retraining on corrupted inputs would bake the fault into the model.
        action = "INVESTIGATE DATA PIPELINE"
    elif data_level == "WATCH":
        action = "MONITOR CLOSELY"
    else:
        action = "NO ACTION"
    positive = preds[TARGET] > 0
    return {
        "batch": name, "rows": int(len(batch)),
        "zero_queue_share": float((preds[TARGET] == 0).mean()),
        "occupied_lane_share": float((pd.to_numeric(batch["vehicle_count"]) > 0).mean()),
        "feature_psi": psi, "worst_feature": worst_feature,
        "data_drift_level": data_level, "performance_drift_level": perf_level,
        "model_metrics": model, "persistence_metrics": persistence,
        "model_metrics_positive_target": metric_set(preds.loc[positive, TARGET], preds.loc[positive, "prediction_m"]) if positive.any() else None,
        "mae_change_vs_approved": degradation, "beats_persistence_by_5pct": bool(beats_baseline),
        "categorical_coverage": monitor["categorical_coverage"],
        "alerts": alerts, "action": action,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--reference", type=Path, default=HERE / "datasets/osm_v2b/splits/train.csv")
    ap.add_argument("--batch", action="append", required=True, help="NAME=path/to/labeled.csv (repeatable)")
    ap.add_argument("--model", type=Path, default=ROOT / "models/bengaluru/bengaluru_queue_hurdle_v1_2026-11.joblib")
    ap.add_argument("--metadata", type=Path, default=ROOT / "src/api/bengaluru_deployment_metadata.json")
    # Test MAE of the production model at approval. v2 (8da60b0e): 0.0558 m; v1 (167b523f) was 0.0550 m.
    ap.add_argument("--approved-test-mae", type=float, default=0.0557631814330094)
    ap.add_argument("--output-dir", type=Path, default=ROOT / "reports/phase3_drift")
    a = ap.parse_args()

    model, meta, digest = load_verified_model(a.model, a.metadata)
    reference = pd.read_csv(a.reference)
    a.output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for spec in a.batch:
        name, _, path = spec.partition("=")
        batch = pd.read_csv(path)
        preds = predict_batch(model, batch)
        pred_path = a.output_dir / f"{name}_predictions.csv"
        preds.to_csv(pred_path, index=False)
        monitor = run_monitor(a.reference, Path(path), pred_path, a.metadata, a.model)
        results.append(assess(name, batch, preds, monitor, a.approved_test_mae, reference))
        print(f"[{results[-1]['action']}] {name}: rows={len(batch)} worst PSI={results[-1]['feature_psi'][results[-1]['worst_feature']]:.3f} "
              f"({results[-1]['worst_feature']}) MAE={results[-1]['model_metrics']['mae_m']:.4f}", flush=True)
        for alert in results[-1]["alerts"]:
            print("   ", alert, flush=True)

    report = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "model_version": meta["model_version"], "model_sha256": digest,
              "reference": str(a.reference.name), "policy": {"psi_watch": PSI_WATCH, "psi_alert": PSI_ALERT,
              "mae_degradation_alert": MAE_DEGRADATION_ALERT, "unknown_category_alert": UNKNOWN_CATEGORY_ALERT, "quality_gate_margin_vs_persistence": GATE_MARGIN},
              "approved_test_mae_m": a.approved_test_mae, "batches": results}
    (a.output_dir / "drift_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"report: {a.output_dir / 'drift_report.json'}")


if __name__ == "__main__":
    main()
