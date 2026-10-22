from pathlib import Path
import xml.etree.ElementTree as ET

import mlflow
from mlflow.tracking import MlflowClient

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "mlflow.db"
REPORTS = ROOT / "reports"
MODELS = ROOT / "models"
DATA = ROOT / "data" / "processed"

mlflow.set_tracking_uri(f"sqlite:///{DB_PATH.as_posix()}")
mlflow.set_experiment("traffic-digital-twin-sumo")
client = MlflowClient()

def log_existing_file(path, artifact_path):
    if path.exists():
        mlflow.log_artifact(str(path), artifact_path=artifact_path)
    else:
        print(f"WARNING: artifact not found: {path}")

def log_queue_run(name, model_file, horizon, metrics, dataset_file):
    with mlflow.start_run(run_name=name):
        mlflow.log_params({
            "task": "queue_prediction",
            "model": "RandomForestRegressor",
            "prediction_horizon_seconds": horizon,
            "evaluation_source": "previously recorded chronological holdout",
        })
        mlflow.log_metrics(metrics)
        log_existing_file(MODELS / model_file, "model")
        log_existing_file(DATA / dataset_file, "dataset")
        print(f"Logged queue experiment: {name}")

def read_trip_metrics(xml_path):
    totals = {
        "trip_duration_s": 0.0,
        "waiting_time_s": 0.0,
        "time_loss_s": 0.0,
        "route_length_m": 0.0,
    }
    count = 0

    for _, element in ET.iterparse(xml_path, events=("end",)):
        if element.tag == "tripinfo":
            totals["trip_duration_s"] += float(element.get("duration", 0))
            totals["waiting_time_s"] += float(element.get("waitingTime", 0))
            totals["time_loss_s"] += float(element.get("timeLoss", 0))
            totals["route_length_m"] += float(element.get("routeLength", 0))
            count += 1
            element.clear()

    if count == 0:
        raise ValueError(f"No tripinfo records found in {xml_path}")

    metrics = {f"mean_{key}": value / count for key, value in totals.items()}
    metrics["completed_trips"] = count
    return metrics

def log_controller_run(name, policy, seed, tripinfo_name,
                       summary_name=None, decisions_name=None,
                       predictions_name=None):
    tripinfo = REPORTS / tripinfo_name

    if not tripinfo.exists():
        print(f"WARNING: skipping missing tripinfo: {tripinfo}")
        return

    metrics = read_trip_metrics(tripinfo)

    with mlflow.start_run(run_name=name):
        mlflow.log_params({
            "task": "sumo_controller_evaluation",
            "controller_policy": policy,
            "simulation_seed": seed,
            "network": "4x4 synthetic grid",
            "traffic_demand": "synthetic SUMO routes",
        })
        mlflow.log_metrics(metrics)

        log_existing_file(tripinfo, "simulation")
        if summary_name:
            log_existing_file(REPORTS / summary_name, "simulation")
        if decisions_name:
            log_existing_file(REPORTS / decisions_name, "controller_logs")
        if predictions_name:
            log_existing_file(REPORTS / predictions_name, "predictions")

    print(f"Logged controller experiment: {name} | trips={metrics['completed_trips']}")

# Queue prediction metrics from the existing evaluations.
# Overall metrics and positive-target-only metrics are recorded separately.
log_queue_run(
    "queue_rf_300s_seed42_evaluation",
    "sumo_queue_rf.joblib",
    300,
    {
        "overall_mae_m": 1.285,
        "overall_rmse_m": 2.018,
        "positive_queue_mae_m": 3.380,
        "positive_queue_rmse_m": 3.674,
    },
    "sumo_queue_labeled_300s.csv",
)

log_queue_run(
    "queue_rf_300s_seed7_evaluation",
    "sumo_queue_rf.joblib",
    300,
    {
        "overall_mae_m": 1.190,
        "overall_rmse_m": 1.937,
        "positive_queue_mae_m": 3.104,
        "positive_queue_rmse_m": 3.497,
    },
    "sumo_queue_labeled_300s_seed7.csv",
)

log_queue_run(
    "queue_rf_300s_seed21_evaluation",
    "sumo_queue_rf.joblib",
    300,
    {
        "overall_mae_m": 1.185,
        "overall_rmse_m": 1.921,
        "positive_queue_mae_m": 3.082,
        "positive_queue_rmse_m": 3.449,
    },
    "sumo_queue_labeled_300s_seed21.csv",
)

log_queue_run(
    "queue_rf_60s_seed42_evaluation",
    "sumo_queue_rf_60s.joblib",
    60,
    {
        "overall_mae_m": 1.212,
        "overall_rmse_m": 1.969,
        "positive_queue_mae_m": 3.285,
        "positive_queue_rmse_m": 3.526,
    },
    "sumo_queue_labeled_60s.csv",
)

# Controller evaluations: only log runs backed by existing reports.
controllers = [
    ("fixed_seed7", "fixed_time", 7,
     "fixed_seed7_tripinfo.xml", "fixed_seed7_summary.xml", None, None),
    ("fixed_seed21", "fixed_time", 21,
     "fixed_seed21_tripinfo.xml", "fixed_seed21_summary.xml", None, None),
    ("fixed_seed42", "fixed_time", 42,
     "fixed_seed42_tripinfo.xml", "fixed_seed42_summary.xml", None, None),
    ("adaptive_seed7", "queue_responsive", 7,
     "adaptive_seed7_tripinfo.xml", "adaptive_seed7_summary.xml",
     "adaptive_seed7_control_decisions.csv", None),
    ("adaptive_seed21", "queue_responsive", 21,
     "adaptive_tripinfo.xml", "adaptive_summary.xml",
     "adaptive_control_decisions.csv", None),
    ("predictive_300s_seed42", "predictive_queue_300s", 42,
     "predictive_seed42_tripinfo.xml", "predictive_seed42_summary.xml",
     "predictive_seed42_decisions.csv", "predictive_seed42_predictions.csv"),
    ("predictive_60s_seed42", "predictive_queue_60s", 42,
     "predictive60s_seed42_tripinfo.xml", "predictive60s_seed42_summary.xml",
     "predictive60s_seed42_decisions.csv",
     "predictive60s_seed42_predictions.csv"),
]

for item in controllers:
    log_controller_run(*item)

# Attach the existing aggregate comparison reports in their own run.
with mlflow.start_run(run_name="existing_controller_comparison_reports"):
    mlflow.log_param("task", "controller_comparison_artifacts")
    for filename in (
        "control_comparison.md",
        "control_comparison_by_seed.csv",
        "control_comparison_summary.csv",
    ):
        log_existing_file(REPORTS / filename, "comparison_reports")

print("\nMLflow logging complete.")
print("Tracking URI:", mlflow.get_tracking_uri())
print("Experiment: traffic-digital-twin-sumo")
