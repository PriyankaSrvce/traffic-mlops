"""Tests for local Metaflow model-version manifest verification."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.model_registry_report import build_registry, registry_entry_from_artifact


def make_manifest(run_id, model_name, model_hash):
    return {
        "metaflow_run_id": run_id,
        "model_status": "candidate_passed_validation_quality_gate",
        "target": "queue_length_m_t_plus_60s",
        "horizon_seconds": 60,
        "model_path": f"/old/location/{model_name}",
        "model_sha256": model_hash,
        "test_metrics": {
            "rows": 10,
            "model": {"mae_m": 1.0, "rmse_m": 1.5},
            "persistence": {"mae_m": 2.0, "rmse_m": 3.0},
        },
    }


class ModelRegistryTests(unittest.TestCase):
    def test_metaflow_artifact_is_eligible_only_when_run_gate_and_hash_pass(self):
        blob = b"model-bytes"
        digest = hashlib.sha256(blob).hexdigest()
        entry = registry_entry_from_artifact(
            run_id="42",
            successful=True,
            model_blob=blob,
            model_metadata={"sha256": digest, "validation_status": "passed"},
            registry_record={
                "model_sha256": digest,
                "model_version": "model-v1",
                "dataset_sha256": "data-hash",
                "target": "queue_length_m_t_plus_60s",
                "horizon_seconds": 60,
                "status": "candidate_passed_validation_quality_gate",
                "validation_metrics": {"mae_m": 1.0},
                "test_metrics": {"mae_m": 1.2},
            },
        )

        self.assertTrue(entry["eligible_for_promotion"])
        self.assertTrue(entry["model_hash_matches"])
        self.assertEqual(entry["run_id"], "42")

    def test_metaflow_artifact_rejects_failed_run_or_wrong_horizon(self):
        blob = b"model-bytes"
        digest = hashlib.sha256(blob).hexdigest()
        entry = registry_entry_from_artifact(
            run_id="43",
            successful=False,
            model_blob=blob,
            model_metadata={"sha256": digest, "validation_status": "passed"},
            registry_record={
                "model_sha256": digest,
                "target": "queue_length_m_t_plus_60s",
                "horizon_seconds": 300,
                "status": "candidate_passed_validation_quality_gate",
            },
        )

        self.assertFalse(entry["eligible_for_promotion"])

    def test_matching_model_hash_is_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report_dir, model_dir = root / "reports", root / "models"
            report_dir.mkdir()
            model_dir.mkdir()
            model = model_dir / "version.joblib"
            model.write_bytes(b"model-bytes")
            digest = hashlib.sha256(model.read_bytes()).hexdigest()
            manifest = make_manifest("10", model.name, digest)
            (report_dir / "queue_model_metaflow_10.json").write_text(json.dumps(manifest))

            entries = build_registry(report_dir, model_dir)

            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["registry_check"], "verified")
            self.assertTrue(entries[0]["model_hash_matches"])

    def test_missing_or_mismatched_hash_is_flagged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report_dir, model_dir = root / "reports", root / "models"
            report_dir.mkdir()
            model_dir.mkdir()
            (model_dir / "version.joblib").write_bytes(b"model-bytes")
            manifest = make_manifest("11", "version.joblib", "wrong-hash")
            (report_dir / "queue_model_metaflow_11.json").write_text(json.dumps(manifest))

            entries = build_registry(report_dir, model_dir)

            self.assertEqual(entries[0]["registry_check"], "incomplete_or_hash_mismatch")
            self.assertFalse(entries[0]["model_hash_matches"])


if __name__ == "__main__":
    unittest.main()
