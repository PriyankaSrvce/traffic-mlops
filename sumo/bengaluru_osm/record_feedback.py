"""Create an immutable offline feedback ledger from SUMO held-out replay rows."""
from __future__ import annotations
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
try:
    from .monitoring import KEYS,TARGET
except ImportError:
    from monitoring import KEYS,TARGET

def build_feedback(observations:pd.DataFrame,predictions:pd.DataFrame,metadata:dict,digest:str)->pd.DataFrame:
    if observations.duplicated(KEYS).any() or predictions.duplicated(KEYS).any():raise ValueError("Feedback source contains duplicate keys")
    frame=observations.merge(predictions[KEYS+["prediction_m"]],on=KEYS,how="inner",validate="one_to_one")
    if len(frame)!=len(observations) or len(frame)!=len(predictions):raise ValueError("Feedback predictions and observations are not a complete one-to-one match")
    frame["observed_queue_length_m_t_plus_60s"]=pd.to_numeric(frame[TARGET],errors="raise")
    frame["prediction_error_m"]=frame["prediction_m"]-frame["observed_queue_length_m_t_plus_60s"]
    frame["feedback_model_version"]=metadata["model_version"]
    frame["feedback_model_sha256"]=digest
    frame["feedback_source"]="held_out_sumo_replay"
    frame["feedback_recorded_at_utc"]=datetime.now(timezone.utc).isoformat()
    return frame

def main():
    base=Path(__file__).resolve().parent;root=base.parents[1]
    ap=argparse.ArgumentParser();ap.add_argument("--observations",type=Path,default=base/"datasets/osm_v2b/splits/test.csv");ap.add_argument("--predictions",type=Path,default=base/"datasets/osm_v2b/hurdle_evaluation/test_predictions.csv");ap.add_argument("--metadata",type=Path,default=root/"models/bengaluru/bengaluru_queue_hurdle_v1_2026-11.json");ap.add_argument("--model",type=Path,default=root/"models/bengaluru/bengaluru_queue_hurdle_v1_2026-11.joblib");ap.add_argument("--output",type=Path,default=root/"reports/bengaluru/heldout_feedback_ledger.csv");a=ap.parse_args()
    if a.output.exists():raise SystemExit(f"Refusing to overwrite existing feedback ledger: {a.output}")
    metadata=json.loads(a.metadata.read_text(encoding="utf-8"));digest=hashlib.sha256(a.model.read_bytes()).hexdigest()
    if metadata.get("validation_status")!="passed" or digest!=metadata.get("sha256"):raise SystemExit("Model integrity or validation check failed")
    frame=build_feedback(pd.read_csv(a.observations),pd.read_csv(a.predictions),metadata,digest)
    a.output.parent.mkdir(parents=True,exist_ok=True);frame.to_csv(a.output,index=False)
    print(json.dumps({"rows":len(frame),"source":"held_out_sumo_replay","model_version":metadata["model_version"],"output":str(a.output),"retraining_eligible":False,"reason":"These rows belong to the existing held-out test seeds and must not be merged into training."},indent=2))

if __name__=="__main__":main()
