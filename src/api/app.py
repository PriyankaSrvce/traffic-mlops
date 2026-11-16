"""API for the validated Bengaluru OSM 60-second queue model."""
from __future__ import annotations
import hashlib,hmac,json,logging,os,re,sys,time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Annotated,Literal
import joblib,numpy as np,pandas as pd
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import FileResponse,RedirectResponse,Response
from prometheus_client import CONTENT_TYPE_LATEST,CollectorRegistry,Counter,Gauge,Histogram,generate_latest
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
DASHBOARD_DIR=Path(__file__).resolve().parent/"dashboard"
LOGGER=logging.getLogger("queue_api")
QUEUE_BUCKETS=(0,0.5,1,2,5,10,20,50,100)
SPEED_BUCKETS=(0,1,2,5,10,15,20,30,50,100)
COUNT_BUCKETS=(0,1,2,3,5,8,12,20)
LATENCY_BUCKETS=(0.005,0.01,0.025,0.05,0.1,0.25,0.5,1,2.5,5)
DRIFT_LEVEL={"OK":0,"WATCH":1,"ALERT":2}

def configure_logging()->None:
    """Structured key=value logs to stdout (and to QUEUE_API_LOG_FILE if set). Idempotent."""
    if LOGGER.handlers:return
    fmt=logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    stream=logging.StreamHandler();stream.setFormatter(fmt);LOGGER.addHandler(stream)
    log_file=os.environ.get("QUEUE_API_LOG_FILE")
    if log_file:
        Path(log_file).parent.mkdir(parents=True,exist_ok=True)
        rotating=RotatingFileHandler(log_file,maxBytes=2_000_000,backupCount=3,encoding="utf-8");rotating.setFormatter(fmt);LOGGER.addHandler(rotating)
    LOGGER.setLevel(os.environ.get("LOG_LEVEL","INFO").upper());LOGGER.propagate=False

def build_metrics()->dict:
    """Prometheus metrics on a per-app registry (so tests can create several apps)."""
    registry=CollectorRegistry()
    return {"registry":registry,
     "requests":Counter("queue_api_requests_total","HTTP requests by route, method and status",["path","method","status"],registry=registry),
     "latency":Histogram("queue_api_request_duration_seconds","HTTP request latency by route",["path"],buckets=LATENCY_BUCKETS,registry=registry),
     "predictions":Counter("queue_predictions_total","Successful predictions served",registry=registry),
     "prediction_failures":Counter("queue_prediction_failures_total","Predictions rejected by output quality checks",registry=registry),
     "predicted":Histogram("queue_predicted_length_m","Predicted queue length 60 s ahead (metres)",buckets=QUEUE_BUCKETS,registry=registry),
     "input_queue":Histogram("queue_input_queue_length_m","Input feature: current queue length (metres)",buckets=QUEUE_BUCKETS,registry=registry),
     "input_speed":Histogram("queue_input_mean_speed_mps","Input feature: mean lane speed (m/s)",buckets=SPEED_BUCKETS,registry=registry),
     "input_vehicles":Histogram("queue_input_vehicle_count","Input feature: vehicles on the lane",buckets=COUNT_BUCKETS,registry=registry),
     "model_loaded":Gauge("queue_model_loaded","1 if a hash-verified model is loaded",registry=registry),
     "model_info":Gauge("queue_model_info","Served model identity (value is always 1)",["model_version","model_sha256"],registry=registry),
     "drift_psi":Gauge("queue_drift_worst_psi","Worst feature PSI of the last offline drift check, per batch",["batch"],registry=registry),
     "drift_mae":Gauge("queue_drift_batch_mae_m","MAE of the last offline drift check, per batch and predictor",["batch","predictor"],registry=registry),
     "drift_level":Gauge("queue_drift_alert_level","Drift level of the last offline check: 0 OK, 1 WATCH, 2 ALERT",["batch","kind"],registry=registry),
     "feedback":Counter("queue_feedback_total","Ground-truth feedback records received",registry=registry),
     "feedback_error":Counter("queue_feedback_abs_error_m_total","Sum of |predicted - actual| over feedback records (metres)",["predictor"],registry=registry),
     "drift_threshold":Gauge("queue_drift_psi_threshold","PSI policy thresholds",["level"],registry=registry)}

def publish_drift_snapshot(metrics:dict)->None:
    """Expose the committed offline drift report as gauges so Grafana can chart it."""
    try:data=json.loads((DASHBOARD_DIR/"dashboard_data.json").read_text(encoding="utf-8"))["drift"]
    except (OSError,json.JSONDecodeError,KeyError):
        LOGGER.warning("drift_snapshot status=missing");return
    metrics["drift_threshold"].labels("watch").set(data["policy"]["psi_watch"]);metrics["drift_threshold"].labels("alert").set(data["policy"]["psi_alert"])
    for b in data["batches"]:
        metrics["drift_psi"].labels(b["batch"]).set(b["worst_psi"])
        metrics["drift_mae"].labels(b["batch"],"model").set(b["model_mae"]);metrics["drift_mae"].labels(b["batch"],"persistence").set(b["persistence_mae"])
        metrics["drift_level"].labels(b["batch"],"data").set(DRIFT_LEVEL.get(b["data_drift_level"],0))
        metrics["drift_level"].labels(b["batch"],"performance").set(DRIFT_LEVEL.get(b["performance_drift_level"],0))

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

class FeedbackRequest(BaseModel):
    """Ground truth that arrives after the 60 s horizon: what the queue really was."""
    model_config=ConfigDict(extra="forbid")
    lane_id:Annotated[str,Field(min_length=1)]
    predicted_queue_length_m:Annotated[float,Field(ge=0,allow_inf_nan=False)]
    actual_queue_length_m:Annotated[float,Field(ge=0,allow_inf_nan=False)]
    queue_length_m_at_prediction:Annotated[float,Field(ge=0,allow_inf_nan=False)]

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
    configure_logging();metrics=build_metrics();app.state.metrics=metrics
    try:
        model,digest,metadata=load_model(selected,os.environ.get("QUEUE_MODEL_SHA256"),meta_path)
        app.state.model=model;app.state.model_sha256=digest;app.state.model_path=str(selected);app.state.metadata=metadata
        metrics["model_loaded"].set(1);metrics["model_info"].labels(metadata["model_version"],digest).set(1)
        LOGGER.info("model_loaded version=%s sha256=%s validation_status=%s",metadata["model_version"],digest,metadata["validation_status"])
    except FileNotFoundError:
        app.state.model=None;app.state.model_sha256=None;app.state.model_path=str(selected);app.state.metadata=None
        metrics["model_loaded"].set(0);LOGGER.warning("model_missing file=%s detail=serving_503_until_artifact_is_configured",selected.name)
    except ValueError as exc:
        # Hash/metadata mismatch: log why, then refuse to start (never serve an unverified model).
        LOGGER.error("model_rejected reason=%s",exc);raise
    publish_drift_snapshot(metrics)
    @app.middleware("http")
    async def observe(request:Request,call_next):
        start=time.perf_counter()
        try:response=await call_next(request)
        except Exception:
            LOGGER.exception("request_failed method=%s path=%s",request.method,request.url.path);raise
        path=getattr(request.scope.get("route"),"path","unmatched");elapsed=time.perf_counter()-start
        if path!="/metrics":
            metrics["requests"].labels(path,request.method,str(response.status_code)).inc();metrics["latency"].labels(path).observe(elapsed)
            level=logging.DEBUG if path in ("/health","/api/v1/health") else logging.WARNING if response.status_code>=400 else logging.INFO
            LOGGER.log(level,"request method=%s path=%s status=%s duration_ms=%.1f",request.method,path,response.status_code,elapsed*1000)
        return response
    @app.get("/metrics",include_in_schema=False)
    def prometheus_metrics():
        return Response(generate_latest(metrics["registry"]),media_type=CONTENT_TYPE_LATEST)
    @app.get("/reports/evidently/{name}",include_in_schema=False)
    def evidently_report(name:str):
        """Serve a packaged Evidently HTML drift report by its batch name."""
        if name=="evidently_bundle.js":page,media=DASHBOARD_DIR/"evidently"/name,"text/javascript"
        elif re.fullmatch(r"[a-z0-9_]{1,60}",name):page,media=DASHBOARD_DIR/"evidently"/(name+".html"),"text/html"
        else:raise HTTPException(status_code=404,detail="Unknown report")
        if not page.is_file():raise HTTPException(status_code=404,detail="Unknown report")
        return FileResponse(page,media_type=media)
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
    @app.get("/",include_in_schema=False)
    def root():
        return RedirectResponse("/dashboard")
    @app.get("/dashboard",include_in_schema=False)
    def dashboard():
        page=DASHBOARD_DIR/"index.html"
        if not page.is_file():raise HTTPException(status_code=404,detail="Dashboard is not packaged")
        return FileResponse(page,media_type="text/html",headers={"Cache-Control":"no-cache"})
    @app.get("/api/v1/dashboard-data")
    def dashboard_data():
        """Versioned Phase 3 snapshot (pipeline, drift, versions, governance) shown on /dashboard."""
        try:return json.loads((DASHBOARD_DIR/"dashboard_data.json").read_text(encoding="utf-8"))
        except (OSError,json.JSONDecodeError) as exc:raise HTTPException(status_code=404,detail="Dashboard data is not packaged") from exc
    @app.post("/predict")
    @app.post("/api/v1/predict")
    def predict(request:PredictionRequest):
        if app.state.model is None:raise HTTPException(status_code=503,detail="Validated Bengaluru model artifact is not configured")
        try:
            features=app.state.metadata["features"]
            raw=np.asarray(app.state.model.predict(features_from_request(request,features)),dtype=float).reshape(-1)
            if raw.size!=1 or not np.isfinite(raw[0]) or raw[0]<0:raise ValueError("Invalid model output")
        except (ValueError,TypeError,KeyError) as exc:
            metrics["prediction_failures"].inc();LOGGER.error("prediction_failed lane_id=%s reason=%s",request.lane_id,exc)
            raise HTTPException(status_code=500,detail="Model failed prediction quality checks") from exc
        metrics["predictions"].inc();metrics["predicted"].observe(float(raw[0]))
        metrics["input_queue"].observe(request.queue_length_m);metrics["input_speed"].observe(request.mean_speed_mps);metrics["input_vehicles"].observe(request.vehicle_count)
        LOGGER.info("prediction lane_id=%s queue_now_m=%.2f vehicles=%d speed_mps=%.2f predicted_m=%.3f model_sha256=%s",
                    request.lane_id,request.queue_length_m,request.vehicle_count,request.mean_speed_mps,float(raw[0]),app.state.model_sha256[:12])
        return {"predicted_queue_length_m":float(raw[0]),"target":TARGET,"horizon_seconds":HORIZON_SECONDS,"model_version":app.state.metadata["model_version"],"model_sha256":app.state.model_sha256}
    @app.post("/api/v1/feedback")
    def feedback(record:FeedbackRequest):
        """Record the observed queue for an earlier prediction so live error can be monitored."""
        model_error=abs(record.predicted_queue_length_m-record.actual_queue_length_m)
        persistence_error=abs(record.queue_length_m_at_prediction-record.actual_queue_length_m)
        metrics["feedback"].inc();metrics["feedback_error"].labels("model").inc(model_error);metrics["feedback_error"].labels("persistence").inc(persistence_error)
        LOGGER.info("feedback lane_id=%s predicted_m=%.3f actual_m=%.3f abs_error_m=%.3f persistence_abs_error_m=%.3f",
                    record.lane_id,record.predicted_queue_length_m,record.actual_queue_length_m,model_error,persistence_error)
        return {"recorded":True,"abs_error_m":model_error,"persistence_abs_error_m":persistence_error}
    return app

app=create_app()
