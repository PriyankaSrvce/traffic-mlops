"""API for the validated Bengaluru OSM 60-second queue model."""
from __future__ import annotations
import hashlib,hmac,json,os,sys
from pathlib import Path
from typing import Annotated,Literal
import joblib,numpy as np,pandas as pd
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator

ROOT=Path(__file__).resolve().parents[2]
OSM_MODEL_DIR=ROOT/"sumo"/"bengaluru_osm"
if str(OSM_MODEL_DIR) not in sys.path:sys.path.insert(0,str(OSM_MODEL_DIR))
from bengaluru_model import HurdleQueueModel  # noqa: F401; joblib requires this stable module path

MODEL_VERSION="bengaluru_queue_hurdle_v1_2026-11"
DEFAULT_MODEL=ROOT/"models"/"bengaluru"/(MODEL_VERSION+".joblib")
DEFAULT_METADATA=ROOT/"models"/"bengaluru"/(MODEL_VERSION+".json")
FEATURES=["queue_length_m","vehicle_count","halting_vehicle_count","mean_speed_mps","phase_elapsed_s","intersection_id","approach_id","lane_id","signal_phase_id","signal_state","vehicle_composition"]
TARGET="queue_length_m_t_plus_60s"
HORIZON_SECONDS=60

class PredictionRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    queue_length_m:Annotated[float,Field(ge=0,allow_inf_nan=False)]
    vehicle_count:Annotated[int,Field(ge=0)]
    halting_vehicle_count:Annotated[int,Field(ge=0)]
    mean_speed_mps:Annotated[float,Field(ge=0,allow_inf_nan=False)]
    phase_elapsed_s:Annotated[float,Field(ge=0,allow_inf_nan=False)]
    intersection_id:Annotated[str,Field(min_length=1)]
    approach_id:Annotated[str,Field(min_length=1)]
    lane_id:Annotated[str,Field(min_length=1)]
    signal_phase_id:Annotated[str,Field(min_length=1)]
    signal_state:Annotated[str,Field(min_length=1)]
    vehicle_composition:Literal["balanced_assumed","motorcycle_heavy_assumed"]
    @field_validator("intersection_id","approach_id","lane_id","signal_phase_id","signal_state",mode="before")
    @classmethod
    def nonblank_identifier(cls,value):
        if isinstance(value,str):
            value=value.strip()
            if not value:raise ValueError("identifier must not be blank")
        return value
    @model_validator(mode="after")
    def count_consistency(self):
        if self.halting_vehicle_count>self.vehicle_count:raise ValueError("halting_vehicle_count cannot exceed vehicle_count")
        return self

def features_from_request(request:PredictionRequest,features=None)->pd.DataFrame:
    names=features or FEATURES
    return pd.DataFrame([{n:getattr(request,n) for n in names}],columns=names)

def sha256_file(path:Path)->str:
    digest=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):digest.update(chunk)
    return digest.hexdigest()

def read_metadata(path:Path)->dict:
    try:metadata=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as exc:raise ValueError(f"Model metadata is missing or invalid: {path}") from exc
    if metadata.get("validation_status")!="passed":raise ValueError("Refusing to load a model without passed Bengaluru validation metadata")
    if metadata.get("network")!="bengaluru_osm_sim.net.xml":raise ValueError("Model metadata network does not match Bengaluru OSM simulation network")
    features=metadata.get("features")
    if not isinstance(features,list) or not features or not set(features)<=set(FEATURES):raise ValueError("Model metadata feature schema is invalid")
    return metadata

def load_model(model_path:Path,expected_sha256:str|None=None,metadata_path:Path|None=None):
    model_path=Path(model_path)
    if not model_path.is_file():raise FileNotFoundError(f"Model artifact not found: {model_path}")
    meta_path=metadata_path or Path(os.environ.get("QUEUE_MODEL_METADATA_PATH",str(model_path.with_suffix(".json"))))
    metadata=read_metadata(meta_path)
    digest=sha256_file(model_path)
    expected=expected_sha256 or metadata.get("sha256")
    if not isinstance(expected,str) or len(expected)!=64:
        raise ValueError("Expected model SHA-256 must be recorded in metadata or QUEUE_MODEL_SHA256")
    try:int(expected,16)
    except ValueError as exc:raise ValueError("Expected model SHA-256 must be hexadecimal") from exc
    if not hmac.compare_digest(digest.lower(),expected.lower()):raise ValueError("Model SHA-256 does not match the configured or recorded digest")
    # Only deserialize after the file digest and validation metadata are trusted.
    model=joblib.load(model_path)
    if list(getattr(model,"feature_names_in_",[]))!=metadata["features"]:raise ValueError("Serialized model schema differs from its metadata")
    return model,digest,metadata

def resolve_model_path(model_path:Path|None=None)->Path:
    selected=Path(os.environ.get("QUEUE_MODEL_PATH",str(model_path or DEFAULT_MODEL)))
    if not selected.is_absolute():selected=(Path.cwd()/selected).resolve()
    return selected

def create_app(model_path:Path|None=None,metadata_path:Path|None=None)->FastAPI:
    app=FastAPI(title="Bengaluru OSM Queue Prediction API",description="Predicts simulated queue length 60 seconds ahead for an OSM-derived Bengaluru corridor and documented synthetic demand. It is not a real-time traffic feed or field-validated forecast.",version="2.0.0")
    selected=resolve_model_path(model_path)
    meta_path=metadata_path or Path(os.environ.get("QUEUE_MODEL_METADATA_PATH",str(selected.with_suffix(".json"))))
    try:
        model,digest,metadata=load_model(selected,os.environ.get("QUEUE_MODEL_SHA256"),meta_path)
        app.state.model=model;app.state.model_sha256=digest;app.state.model_path=str(selected);app.state.metadata=metadata
    except FileNotFoundError:
        app.state.model=None;app.state.model_sha256=None;app.state.model_path=str(selected);app.state.metadata=None
    @app.get("/health")
    @app.get("/api/v1/health")
    def health():
        if app.state.model is None:raise HTTPException(status_code=503,detail="Validated Bengaluru model artifact is not configured")
        return {"status":"ok","model_loaded":True,"validation_status":app.state.metadata["validation_status"]}
    @app.get("/model-info")
    @app.get("/api/v1/model-info")
    def model_info():
        if app.state.model is None:raise HTTPException(status_code=503,detail="Validated Bengaluru model artifact is not configured")
        m=app.state.metadata
        return {"model_version":m["model_version"],"model_sha256":app.state.model_sha256,"target":TARGET,"horizon_seconds":HORIZON_SECONDS,"queue_unit":"metres","queue_measurement":m.get("queue_measurement_schema"),"network":m["network"],"validation_status":m["validation_status"],"features":m["features"]}
    @app.post("/predict")
    @app.post("/api/v1/predict")
    def predict(request:PredictionRequest):
        if app.state.model is None:raise HTTPException(status_code=503,detail="Validated Bengaluru model artifact is not configured")
        try:
            features=app.state.metadata["features"]
            raw=np.asarray(app.state.model.predict(features_from_request(request,features)),dtype=float).reshape(-1)
            if raw.size!=1 or not np.isfinite(raw[0]) or raw[0]<0:raise ValueError("Invalid model output")
        except (ValueError,TypeError,KeyError) as exc:raise HTTPException(status_code=500,detail="Model failed prediction quality checks") from exc
        return {"predicted_queue_length_m":float(raw[0]),"target":TARGET,"horizon_seconds":HORIZON_SECONDS,"model_version":app.state.metadata["model_version"],"model_sha256":app.state.model_sha256}
    return app

app=create_app()
