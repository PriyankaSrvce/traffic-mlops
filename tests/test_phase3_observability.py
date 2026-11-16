"""Phase 3: Python logging and Prometheus metrics of the prediction API (through real HTTP calls)."""
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.api.app import FEATURES, HORIZON_SECONDS, LOGGER, MODEL_VERSION, TARGET, create_app

VALID = {"queue_length_m": 2.5, "vehicle_count": 8, "halting_vehicle_count": 3, "mean_speed_mps": 4.2,
         "phase_elapsed_s": 18.0, "intersection_id": "4105324822", "approach_id": "1109948890#1",
         "lane_id": "1109948890#1_0", "signal_phase_id": "1", "signal_state": "GGrr",
         "vehicle_composition": "balanced_assumed"}


class ObservabilityFakeModel:
    def __init__(self, features, out=(2.5,)):
        self.feature_names_in_ = np.asarray(features)
        self.out = np.asarray(out, dtype=float)

    def predict(self, x):
        return self.out


def write_model(root: Path, out=(2.5,)):
    model_path, metadata_path = root / "model.joblib", root / "model.json"
    joblib.dump(ObservabilityFakeModel(FEATURES, out), model_path)
    metadata = {"model_version": MODEL_VERSION, "sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
                "target": TARGET, "horizon_seconds": HORIZON_SECONDS, "features": FEATURES,
                "network": "bengaluru_osm_sim.net.xml", "validation_status": "passed"}
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    return model_path, metadata_path, metadata


@pytest.fixture()
def client(tmp_path):
    model_path, metadata_path, _ = write_model(tmp_path)
    return TestClient(create_app(model_path, metadata_path))


@pytest.fixture()
def api_log(caplog):
    """The API logger does not propagate to root, so attach pytest's handler to it directly."""
    LOGGER.addHandler(caplog.handler)
    caplog.set_level("DEBUG", logger="queue_api")
    yield caplog
    LOGGER.removeHandler(caplog.handler)


def metric_value(text: str, prefix: str) -> float:
    lines = [line for line in text.splitlines() if line.startswith(prefix)]
    assert lines, f"metric not exposed: {prefix}"
    return float(lines[0].rsplit(" ", 1)[1])


def test_metrics_endpoint_exposes_model_identity_and_drift_snapshot(client):
    text = client.get("/metrics").text
    assert metric_value(text, "queue_model_loaded") == 1
    assert 'queue_model_info{model_sha256="' in text
    assert 'queue_drift_worst_psi{batch="sensor_fault_kmh"}' in text
    assert metric_value(text, 'queue_drift_psi_threshold{level="alert"}') == 0.25


def test_prediction_updates_counters_and_feature_histograms(client):
    for _ in range(3):
        assert client.post("/api/v1/predict", json=VALID).status_code == 200
    text = client.get("/metrics").text
    assert metric_value(text, "queue_predictions_total") == 3
    assert metric_value(text, "queue_predicted_length_m_sum") == pytest.approx(7.5)
    assert metric_value(text, "queue_input_mean_speed_mps_sum") == pytest.approx(12.6)
    assert metric_value(text, 'queue_api_requests_total{method="POST",path="/api/v1/predict",status="200"}') == 3


def test_rejected_request_is_counted_by_status_and_not_as_prediction(client):
    assert client.post("/api/v1/predict", json={**VALID, "queue_length_m": -1}).status_code == 422
    text = client.get("/metrics").text
    assert metric_value(text, "queue_predictions_total") == 0
    assert metric_value(text, 'queue_api_requests_total{method="POST",path="/api/v1/predict",status="422"}') == 1


def test_prediction_and_startup_are_logged_with_model_hash(tmp_path, api_log):
    model_path, metadata_path, metadata = write_model(tmp_path)
    app_client = TestClient(create_app(model_path, metadata_path))
    app_client.post("/api/v1/predict", json=VALID)
    messages = [r.getMessage() for r in api_log.records]
    assert any(m.startswith("model_loaded") and metadata["sha256"] in m for m in messages)
    prediction = next(m for m in messages if m.startswith("prediction "))
    assert "lane_id=1109948890#1_0" in prediction and "predicted_m=2.500" in prediction
    assert metadata["sha256"][:12] in prediction


def test_invalid_model_output_is_logged_as_error_and_counted(tmp_path, api_log):
    model_path, metadata_path, _ = write_model(tmp_path, out=(-4.0,))
    app_client = TestClient(create_app(model_path, metadata_path))
    assert app_client.post("/api/v1/predict", json=VALID).status_code == 500
    assert any(r.levelname == "ERROR" and r.getMessage().startswith("prediction_failed") for r in api_log.records)
    assert metric_value(app_client.get("/metrics").text, "queue_prediction_failures_total") == 1


def test_hash_mismatch_is_logged_and_startup_refused(tmp_path, api_log, monkeypatch):
    model_path, metadata_path, _ = write_model(tmp_path)
    monkeypatch.setenv("QUEUE_MODEL_SHA256", "0" * 64)
    with pytest.raises(ValueError):
        create_app(model_path, metadata_path)
    assert any(r.levelname == "ERROR" and r.getMessage().startswith("model_rejected") for r in api_log.records)


def test_evidently_route_rejects_path_tricks(client):
    assert client.get("/reports/evidently/..%2Fdashboard_data").status_code == 404
    assert client.get("/reports/evidently/no_such_report").status_code == 404


def test_feedback_updates_live_error_counters_for_model_and_baseline(client, api_log):
    body = {"lane_id": "1109948890#1_0", "predicted_queue_length_m": 2.5, "actual_queue_length_m": 4.0,
            "queue_length_m_at_prediction": 1.0}
    response = client.post("/api/v1/feedback", json=body)
    assert response.status_code == 200 and response.json()["abs_error_m"] == pytest.approx(1.5)
    text = client.get("/metrics").text
    assert metric_value(text, "queue_feedback_total") == 1
    assert metric_value(text, 'queue_feedback_abs_error_m_total{predictor="model"}') == pytest.approx(1.5)
    assert metric_value(text, 'queue_feedback_abs_error_m_total{predictor="persistence"}') == pytest.approx(3.0)
    assert any(r.getMessage().startswith("feedback lane_id=") for r in api_log.records)


def test_feedback_rejects_negative_queue_values(client):
    body = {"lane_id": "x", "predicted_queue_length_m": 1.0, "actual_queue_length_m": -2.0, "queue_length_m_at_prediction": 0.0}
    assert client.post("/api/v1/feedback", json=body).status_code == 422
