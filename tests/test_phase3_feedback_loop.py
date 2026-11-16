"""Phase 3 feedback loop: retraining trigger policy, replay payloads, Evidently summary parsing."""
import json

import pytest

from scripts.replay_production_traffic import to_request
from scripts.retraining_trigger import decide
from sumo.bengaluru_osm.evidently_drift_report import BUNDLE_NAME, share_script_bundle, summarize


def batch(name, data="OK", performance="OK", alerts=()):
    return {"batch": name, "data_drift_level": data, "performance_drift_level": performance, "alerts": list(alerts)}


def test_performance_alert_triggers_retraining_with_reasons():
    report = {"model_sha256": "abc", "batches": [batch("normal"), batch("surge", "WATCH", "ALERT", ["PERFORMANCE DRIFT ALERT: +59%"])]}
    decision = decide(report)
    assert decision["retrain"] and decision["decision"] == "TRIGGER_RETRAINING"
    assert decision["performance_alert_batches"] == ["surge"]
    assert decision["reasons"] == ["PERFORMANCE DRIFT ALERT: +59%"]


def test_data_only_alert_never_triggers_retraining():
    decision = decide({"batches": [batch("sensor_fault", "ALERT", "OK", ["DATA DRIFT ALERT"])]})
    assert not decision["retrain"]
    assert decision["pipeline_investigation_batches"] == ["sensor_fault"]


def test_stable_batches_do_not_trigger():
    decision = decide({"batches": [batch("normal"), batch("watch_only", "WATCH")]})
    assert decision["decision"] == "NO_RETRAINING" and decision["performance_alert_batches"] == []


def test_committed_drift_report_triggers_on_surges_only():
    from pathlib import Path
    report = json.loads((Path(__file__).resolve().parents[1] / "reports/phase3_drift/drift_report.json").read_text(encoding="utf-8"))
    decision = decide(report)
    assert decision["performance_alert_batches"] == ["surge_600", "surge_720"]
    assert decision["pipeline_investigation_batches"] == ["sensor_fault_kmh"]


def test_replay_row_becomes_a_valid_api_request():
    from src.api.app import PredictionRequest
    row = {"queue_length_m": "4.5", "vehicle_count": "2.0", "halting_vehicle_count": "1", "mean_speed_mps": "3.25",
           "phase_elapsed_s": "12.0", "intersection_id": "tls1", "approach_id": "a#0", "lane_id": "a#0_0",
           "signal_phase_id": "5", "signal_state": "rrGG", "vehicle_composition": "balanced_assumed",
           "queue_length_m_t_plus_60s": "0.0", "run_id": "ignored"}
    request = PredictionRequest(**to_request(row))
    assert request.vehicle_count == 2 and request.signal_phase_id == "5" and request.mean_speed_mps == 3.25


class FakeSnapshot:
    def dict(self):
        return {"metrics": [
            {"metric_id": "DriftedColumnsCount(drift_share=0.5)", "value": {"count": 1.0, "share": 0.5}},
            {"metric_id": "ValueDrift(column=mean_speed_mps,method=Wasserstein distance (normed),threshold=0.1)", "value": 1.5},
            {"metric_id": "ValueDrift(column=lane_group,method=K-S p_value,threshold=0.05)", "value": 0.4},
            {"metric_id": "MAE(regression_name=default,error_plot=False)", "value": {"mean": 0.0877, "std": 0.6}},
            {"metric_id": "RMSE(regression_name=default)", "value": 0.7},
            {"metric_id": "R2Score(regression_name=default)", "value": 0.84}]}


def test_evidently_summary_reads_distance_and_p_value_tests_correctly():
    result = summarize(FakeSnapshot())
    assert result["drifted_column_names"] == ["mean_speed_mps"]          # distance above threshold = drift
    assert not result["columns"]["lane_group"]["drift_detected"]         # p-value above threshold = no drift
    assert result["model_quality"] == {"mae_m": 0.0877, "rmse_m": 0.7, "r2": 0.84}
    assert result["drifted_columns"] == {"count": 1, "share": 0.5}


def test_shared_bundle_keeps_report_content_and_refuses_a_different_viewer(tmp_path):
    viewer = "var viewer=1;" * 50
    first, second = tmp_path / "a.html", tmp_path / "b.html"
    first.write_text(f"<html><script>var data=1;</script><script>{viewer}</script></html>", encoding="utf-8")
    share_script_bundle(first)
    assert (tmp_path / BUNDLE_NAME).read_text(encoding="utf-8") == viewer
    assert first.read_text(encoding="utf-8") == f'<html><script>var data=1;</script><script src="{BUNDLE_NAME}"></script></html>'
    second.write_text(f"<html><script>{viewer}CHANGED</script></html>", encoding="utf-8")
    with pytest.raises(ValueError):
        share_script_bundle(second)
