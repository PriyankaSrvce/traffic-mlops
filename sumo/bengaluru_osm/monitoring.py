"""Offline model monitoring for held-out Bengaluru SUMO observations.

This is a reproducible batch check, not a live production monitor.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

NUMERIC = ["queue_length_m", "vehicle_count", "halting_vehicle_count", "mean_speed_mps", "phase_elapsed_s", "queue_length_m_t_plus_60s"]
CATEGORICAL = ["intersection_id", "approach_id", "lane_id", "signal_phase_id", "signal_state", "vehicle_composition"]
TARGET = "queue_length_m_t_plus_60s"
KEYS = ["run_id", "seed", "scenario", "vehicle_composition", "intersection_id", "approach_id", "lane_id", "time_s"]

def psi(reference, current, bins=10):
    """Population stability index with reference quantile bins and tail bins."""
    ref = np.asarray(reference, dtype=float); cur = np.asarray(current, dtype=float)
    ref = ref[np.isfinite(ref)]; cur = cur[np.isfinite(cur)]
    if not len(ref) or not len(cur): return None
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins+1)))
    if len(edges) < 2: edges = np.array([ref[0]-0.5, ref[0]+0.5])
    edges[0] = -np.inf; edges[-1] = np.inf
    rp = np.histogram(ref, bins=edges)[0] / len(ref)
    cp = np.histogram(cur, bins=edges)[0] / len(cur)
    rp = np.clip(rp, 1e-6, None); cp = np.clip(cp, 1e-6, None)
    return float(np.sum((cp-rp)*np.log(cp/rp)))

def metric_set(actual, predicted):
    actual=np.asarray(actual,float);predicted=np.asarray(predicted,float)
    return {"n":int(len(actual)),"mae_m":float(mean_absolute_error(actual,predicted)),
            "rmse_m":float(mean_squared_error(actual,predicted)**0.5),"r2":float(r2_score(actual,predicted)) if len(actual)>1 else None}

def run_monitor(reference_path: Path, current_path: Path, predictions_path: Path, metadata_path: Path, model_path: Path):
    ref=pd.read_csv(reference_path);cur=pd.read_csv(current_path);pred=pd.read_csv(predictions_path)
    metadata=json.loads(metadata_path.read_text(encoding="utf-8"))
    digest=hashlib.sha256(model_path.read_bytes()).hexdigest()
    if metadata.get("validation_status")!="passed" or digest!=metadata.get("sha256"):
        raise ValueError("Model metadata or SHA-256 validation failed")
    required=set(KEYS+NUMERIC+CATEGORICAL)
    if missing:=required-set(ref.columns): raise ValueError(f"Reference missing columns: {sorted(missing)}")
    if missing:=required-set(cur.columns): raise ValueError(f"Current batch missing columns: {sorted(missing)}")
    pcols=set(KEYS+[TARGET,"prediction_m"])
    if missing:=pcols-set(pred.columns): raise ValueError(f"Predictions missing columns: {sorted(missing)}")
    if ref.duplicated(KEYS).any() or cur.duplicated(KEYS).any() or pred.duplicated(KEYS).any():
        raise ValueError("Duplicate run/intersection/lane/time keys detected")
    if cur[KEYS].isna().any().any() or pred[KEYS].isna().any().any(): raise ValueError("Missing join keys")
    join=cur[KEYS+NUMERIC].merge(pred[KEYS+[TARGET,"prediction_m"]],on=KEYS,suffixes=("_source","_prediction"),validate="one_to_one")
    if len(join)!=len(cur) or len(join)!=len(pred): raise ValueError("Current batch and prediction rows do not match one-to-one")
    if not np.allclose(join[f"{TARGET}_source"],join[f"{TARGET}_prediction"],atol=1e-6): raise ValueError("Prediction target values do not align with current observations")
    invalid_numeric={c:int((~np.isfinite(pd.to_numeric(cur[c],errors="coerce"))).sum()) for c in NUMERIC}
    invalid_predictions=int((~np.isfinite(pd.to_numeric(pred.prediction_m,errors="coerce")) | (pd.to_numeric(pred.prediction_m,errors="coerce")<0)).sum())
    drift={}
    for feature in NUMERIC:
        score=psi(ref[feature],cur[feature])
        drift[feature]={"psi":score,"status":"high" if score is not None and score>=0.25 else "watch" if score is not None and score>=0.10 else "stable"}
    category_drift={}
    for feature in CATEGORICAL:
        base=set(ref[feature].astype(str));values=cur[feature].astype(str)
        category_drift[feature]={"unknown_rate":float((~values.isin(base)).mean()),"reference_categories":len(base),"current_categories":int(values.nunique())}
    overall=metric_set(join[f"{TARGET}_source"],join.prediction_m)
    by_demand={str(k):metric_set(g[f"{TARGET}_source"],g.prediction_m) for k,g in join.groupby("scenario")}
    by_composition={str(k):metric_set(g[f"{TARGET}_source"],g.prediction_m) for k,g in join.groupby("vehicle_composition")}
    by_intersection={str(k):metric_set(g[f"{TARGET}_source"],g.prediction_m) for k,g in join.groupby("intersection_id")}
    return {"monitor_type":"offline_simulation_batch","model_version":metadata["model_version"],"model_sha256":digest,
      "network":metadata["network"],"target":TARGET,"horizon_seconds":60,"reference_rows":int(len(ref)),"current_rows":int(len(cur)),
      "invalid_inputs":invalid_numeric,"invalid_predictions":invalid_predictions,"feature_drift":drift,"categorical_coverage":category_drift,
      "prediction_distribution_m":{"mean":float(pred.prediction_m.mean()),"p95":float(pred.prediction_m.quantile(.95)),"max":float(pred.prediction_m.max())},
      "observed_queue_distribution_m":{"mean":float(cur[TARGET].mean()),"p95":float(cur[TARGET].quantile(.95)),"max":float(cur[TARGET].max())},
      "prediction_error":overall,"error_by_demand":by_demand,"error_by_composition":by_composition,"error_by_intersection":by_intersection,
      "fallback_events":0,"thresholds":{"psi_watch":0.10,"psi_high":0.25},
      "limitations":"Offline held-out SUMO replay only. No production traffic, live API telemetry, or independently observed field queue labels."}

def main():
    base=Path(__file__).resolve().parent;root=base.parents[1]
    ap=argparse.ArgumentParser();ap.add_argument("--reference",type=Path,default=base/"datasets/osm_v2b/splits/train.csv");ap.add_argument("--current",type=Path,default=base/"datasets/osm_v2b/splits/test.csv");ap.add_argument("--predictions",type=Path,default=base/"datasets/osm_v2b/hurdle_evaluation/test_predictions.csv");ap.add_argument("--metadata",type=Path,default=root/"models/bengaluru/bengaluru_queue_hurdle_v1_2026-11.json");ap.add_argument("--model",type=Path,default=root/"models/bengaluru/bengaluru_queue_hurdle_v1_2026-11.joblib");ap.add_argument("--output",type=Path,default=root/"reports/bengaluru/offline_monitoring.json");a=ap.parse_args()
    result=run_monitor(a.reference,a.current,a.predictions,a.metadata,a.model);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps({"rows":result["current_rows"],"model_version":result["model_version"],"mae_m":result["prediction_error"]["mae_m"],"rmse_m":result["prediction_error"]["rmse_m"],"output":str(a.output)},indent=2))

if __name__=="__main__":main()
