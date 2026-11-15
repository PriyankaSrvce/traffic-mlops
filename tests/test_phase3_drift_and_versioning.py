"""Phase 3: drift detection policy, sensor-fault batch, promotion policy, dashboard routes."""
import json
import unittest

import numpy as np
import pandas as pd

from scripts.model_promotion import decide
from sumo.bengaluru_osm.drift_detection import assess
from sumo.bengaluru_osm.make_sensor_fault_batch import apply_speed_unit_fault
from sumo.bengaluru_osm.monitoring import psi

APPROVED = 0.055


def monitor_stub(psi_values, mae, unknown=0.0):
    return {"feature_drift": {k: {"psi": v} for k, v in psi_values.items()},
            "prediction_error": {"n": 4, "mae_m": mae, "rmse_m": mae, "r2": None},
            "categorical_coverage": {"lane_id": {"unknown_rate": unknown, "reference_categories": 2, "current_categories": 2}}}


def batch_and_preds(persistence_error):
    batch = pd.DataFrame({"vehicle_count": [0, 0, 1, 2]})
    preds = pd.DataFrame({"queue_length_m_t_plus_60s": [0.0, 0.0, 1.0, 2.0],
                          "prediction_m": [0.0, 0.0, 1.0, 2.0],
                          "persistence_m": [persistence_error, 0.0, 1.0, 2.0]})
    return batch, preds


class ZeroInflatedPsiTests(unittest.TestCase):
    def test_psi_sees_shift_hidden_behind_many_zeros(self):
        rng = np.random.default_rng(0)
        ref = np.concatenate([np.zeros(9700), rng.exponential(2.0, 300)])
        same = np.concatenate([np.zeros(9700), rng.exponential(2.0, 300)])
        shifted = np.concatenate([np.zeros(9000), rng.exponential(6.0, 1000)])
        self.assertLess(psi(ref, same), 0.05)
        self.assertGreater(psi(ref, shifted), 0.10)


class DriftPolicyTests(unittest.TestCase):
    def test_stable_batch_needs_no_action(self):
        batch, preds = batch_and_preds(persistence_error=1.0)
        r = assess("normal", batch, preds, monitor_stub({"queue_length_m": 0.01}, mae=0.055), APPROVED)
        self.assertEqual(r["action"], "NO ACTION")

    def test_performance_drift_recommends_retraining(self):
        batch, preds = batch_and_preds(persistence_error=1.0)
        r = assess("surge", batch, preds, monitor_stub({"queue_length_m": 0.12}, mae=0.09), APPROVED)
        self.assertEqual(r["performance_drift_level"], "ALERT")
        self.assertEqual(r["action"], "RETRAINING RECOMMENDED")

    def test_data_only_alert_points_to_pipeline_not_retraining(self):
        batch, preds = batch_and_preds(persistence_error=1.0)
        r = assess("fault", batch, preds, monitor_stub({"mean_speed_mps": 0.77}, mae=0.056), APPROVED)
        self.assertEqual(r["data_drift_level"], "ALERT")
        self.assertEqual(r["action"], "INVESTIGATE DATA PIPELINE")

    def test_unseen_categories_raise_schema_alert(self):
        batch, preds = batch_and_preds(persistence_error=1.0)
        r = assess("new_lanes", batch, preds, monitor_stub({"queue_length_m": 0.0}, mae=0.055, unknown=0.05), APPROVED)
        self.assertEqual(r["data_drift_level"], "ALERT")
        self.assertTrue(any(a.startswith("SCHEMA ALERT") for a in r["alerts"]))


class SensorFaultTests(unittest.TestCase):
    def test_fault_scales_speed_tags_rows_and_keeps_labels(self):
        src = pd.DataFrame({"mean_speed_mps": [0.0, 10.0], "scenario": ["high", "low"],
                            "queue_length_m_t_plus_60s": [0.0, 3.0]})
        out = apply_speed_unit_fault(src)
        self.assertEqual(out["mean_speed_mps"].tolist(), [0.0, 36.0])
        self.assertTrue(out["scenario"].str.endswith("_sensor_fault_kmh").all())
        self.assertEqual(out["queue_length_m_t_plus_60s"].tolist(), [0.0, 3.0])
        self.assertEqual(src["mean_speed_mps"].tolist(), [0.0, 10.0])


class PromotionPolicyTests(unittest.TestCase):
    TABLE = {"original_test": {"production_mae_m": 0.0550, "candidate_mae_m": 0.0555},
             "surge": {"production_mae_m": 0.0877, "candidate_mae_m": 0.0700}}

    def test_candidate_promoted_only_when_all_checks_pass(self):
        r = decide(self.TABLE, ["original_test"], ["surge"], gate_passed=True)
        self.assertTrue(r["promote"])

    def test_regression_on_original_data_blocks_promotion(self):
        table = {**self.TABLE, "original_test": {"production_mae_m": 0.0550, "candidate_mae_m": 0.0600}}
        self.assertFalse(decide(table, ["original_test"], ["surge"], gate_passed=True)["promote"])

    def test_failed_quality_gate_blocks_promotion(self):
        self.assertFalse(decide(self.TABLE, ["original_test"], ["surge"], gate_passed=False)["promote"])


class DashboardRouteTests(unittest.TestCase):
    def test_dashboard_page_and_data_are_packaged(self):
        from pathlib import Path
        from src.api.app import DASHBOARD_DIR
        page = (DASHBOARD_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn("/api/v1/dashboard-data", page)
        data = json.loads((DASHBOARD_DIR / "dashboard_data.json").read_text(encoding="utf-8"))
        for key in ("pipeline", "drift", "versions", "governance", "sample_request"):
            self.assertIn(key, data)
        stages = [v["stage"] for v in data["versions"]]
        self.assertEqual(stages.count("production"), 1)
        self.assertTrue(Path(DASHBOARD_DIR).is_dir())


if __name__ == "__main__":
    unittest.main()
