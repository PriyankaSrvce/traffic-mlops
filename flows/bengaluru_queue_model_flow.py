"""Run the Bengaluru queue-model validation/training workflow with Metaflow.

The flow deliberately delegates fitting to the same checked evaluator used for
the local benchmark, keeping split and acceptance rules identical.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from metaflow import FlowSpec, Parameter, current, step

ROOT = Path(__file__).resolve().parents[1]
EVALUATOR = ROOT / "sumo" / "bengaluru_osm" / "evaluate_hurdle.py"


class BengaluruQueueModelFlow(FlowSpec):
    dataset = Parameter(
        "dataset",
        default=str(ROOT / "sumo" / "bengaluru_osm" / "datasets" / "osm_v2b" / "training_labels_incident_quarantined.csv"),
        help="Validated, incident-quarantined SUMO labels.",
    )
    artifact_root = Parameter(
        "artifact-root",
        default=str(ROOT / "reports" / "metaflow" / "bengaluru"),
        help="Local versioned output root; no remote datastore is configured.",
    )

    @step
    def start(self):
        path = Path(self.dataset)
        if not path.is_file():
            raise FileNotFoundError(path)
        import pandas as pd

        frame = pd.read_csv(path, usecols=["run_id", "seed", "scenario", "queue_length_m_t_plus_60s"])
        if frame.empty or frame.isna().any().any():
            raise ValueError("Training labels are empty or contain missing split/target values")
        groups = frame.groupby("run_id")["seed"].nunique()
        if (groups > 1).any():
            raise ValueError("A run_id maps to more than one seed")
        expected = {7, 42, 2026, 99, 123, 31415}
        if not expected.issubset(set(frame.seed.astype(int).unique())):
            raise ValueError("Dataset does not contain the declared train/validation/test seed groups")
        self.dataset_sha256 = __import__("hashlib").sha256(path.read_bytes()).hexdigest()
        self.rows = int(len(frame))
        self.run_count = int(frame.run_id.nunique())
        self.next(self.train_evaluate)

    @step
    def train_evaluate(self):
        from datetime import datetime

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        root = Path(self.artifact_root) / f"{stamp}-{current.run_id}"
        report_dir = root / "evaluation"
        model_dir = root / "models"
        report_dir.mkdir(parents=True, exist_ok=False)
        model_dir.mkdir(parents=True, exist_ok=False)
        proc = subprocess.run(
            [sys.executable, str(EVALUATOR), "--data", str(Path(self.dataset).resolve()),
             "--output-dir", str(report_dir), "--model-dir", str(model_dir)],
            cwd=ROOT, text=True, capture_output=True,
        )
        (root / "training.log").write_text(proc.stdout + "\n" + proc.stderr, encoding="utf-8")
        if proc.returncode:
            raise RuntimeError(f"Bengaluru evaluator failed ({proc.returncode}): {proc.stderr[-1500:]}")
        report = json.loads((report_dir / "report.json").read_text(encoding="utf-8"))
        metadata_path = model_dir / (report["model_version"] + ".json")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        model_path = model_dir / (report["model_version"] + ".joblib")
        flow_version = f"{report['model_version']}_metaflow_{current.run_id}"
        metadata["model_version"] = flow_version
        metadata["model_path"] = str(model_path)
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        report["model_version"] = flow_version
        report["artifact_sha256"] = report["model_sha256"]
        (report_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        self.output_root = str(root)
        self.report = report
        self.model_blob = model_path.read_bytes()
        self.model_metadata = metadata
        self.next(self.acceptance)

    @step
    def acceptance(self):
        if self.report.get("validation_status") != "passed" or not all(self.report.get("acceptance_gate", {}).values()):
            raise ValueError("Candidate failed the predeclared validation and held-out acceptance gates")
        self.model_sha256 = self.report["model_sha256"]
        self.model_version = self.report["model_version"]
        self.validation_metrics = self.report["validation"]
        self.test_metrics = self.report["test"]
        self.registry_status = "candidate_passed_validation_quality_gate"
        self.registry_record = {
            "run_id": str(current.run_id),
            "model_version": self.model_version,
            "model_sha256": self.model_sha256,
            "dataset_sha256": self.dataset_sha256,
            "target": self.report["target"],
            "horizon_seconds": 60,
            "status": self.registry_status,
            "validation_metrics": self.validation_metrics,
            "test_metrics": self.test_metrics,
        }
        self.next(self.end)

    @step
    def end(self):
        print(json.dumps({"rows": self.rows, "runs": self.run_count, "dataset_sha256": self.dataset_sha256,
                          "model_version": self.model_version, "model_sha256": self.model_sha256,
                          "registry_status": self.registry_status,
                          "validation": self.validation_metrics, "test": self.test_metrics,
                          "artifact_root": self.output_root}, indent=2))


if __name__ == "__main__":
    BengaluruQueueModelFlow()
