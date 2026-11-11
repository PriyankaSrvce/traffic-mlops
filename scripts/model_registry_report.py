"""Inspect and export models versioned as Metaflow artifacts.

The registry is backed by the configured Metaflow metadata/datastore. With the
default local configuration it is machine-local; a shared registry requires a
team-managed remote Metaflow datastore and metadata service.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"
MODEL_DIR = ROOT / "models"


def registry_entry_from_artifact(
    *,
    run_id: str,
    successful: bool,
    model_blob: bytes | None,
    model_metadata: dict,
    registry_record: dict,
) -> dict:
    """Validate one Metaflow model artifact and return a safe catalog entry."""
    expected_hash = registry_record.get("model_sha256")
    actual_hash = hashlib.sha256(model_blob).hexdigest() if model_blob is not None else None
    hash_matches = actual_hash is not None and actual_hash.lower() == str(expected_hash).lower()
    gates_passed = bool(
        registry_record.get("status") == "candidate_passed_validation_quality_gate"
        and model_metadata.get("validation_status") == "passed"
        and model_metadata.get("sha256", expected_hash) == expected_hash
        and registry_record.get("target") == "queue_length_m_t_plus_60s"
        and registry_record.get("horizon_seconds") == 60
    )
    eligible = bool(successful and hash_matches and gates_passed)
    return {
        "run_id": str(run_id),
        "model_version": registry_record.get("model_version"),
        "target": registry_record.get("target"),
        "horizon_seconds": registry_record.get("horizon_seconds"),
        "dataset_sha256": registry_record.get("dataset_sha256"),
        "model_sha256": expected_hash,
        "actual_model_sha256": actual_hash,
        "model_hash_matches": hash_matches,
        "metaflow_run_successful": bool(successful),
        "validation_status": model_metadata.get("validation_status"),
        "registry_status": registry_record.get("status"),
        "eligible_for_promotion": eligible,
        "validation_metrics": registry_record.get("validation_metrics"),
        "test_metrics": registry_record.get("test_metrics"),
    }


def build_registry(report_dir=REPORT_DIR, model_dir=MODEL_DIR):
    """Read legacy JSON manifests and verify their adjacent local model files."""
    runs = []
    for manifest in report_dir.glob("queue_model_metaflow_*.json"):
        record = json.loads(manifest.read_text(encoding="utf-8"))
        model_path = model_dir / Path(record["model_path"]).name
        expected_hash = record.get("model_sha256")
        model_hash_matches = (
            model_path.is_file()
            and expected_hash is not None
            and hashlib.sha256(model_path.read_bytes()).hexdigest() == expected_hash
        )
        test = record["test_metrics"]
        runs.append({
            "run_id": str(record["metaflow_run_id"]),
            "manifest": str(manifest.relative_to(report_dir.parent)),
            "status": record.get("model_status", "unknown"),
            "registry_check": "verified" if model_hash_matches else "incomplete_or_hash_mismatch",
            "target": record["target"],
            "horizon_seconds": record["horizon_seconds"],
            "model_path": str(model_path.relative_to(model_dir.parent)),
            "model_sha256": expected_hash,
            "model_hash_matches": model_hash_matches,
            "test_rows": test["rows"],
            "test_mae_m": test["model"]["mae_m"],
            "test_rmse_m": test["model"]["rmse_m"],
            "persistence_test_mae_m": test["persistence"]["mae_m"],
            "persistence_test_rmse_m": test["persistence"]["rmse_m"],
        })
    runs.sort(key=lambda item: item["run_id"])
    return runs


def get_metaflow_run(flow_name: str, run_id: str):
    """Resolve a specific run through Metaflow's configured metadata service."""
    from metaflow import Run

    return Run(f"{flow_name}/{run_id}")


def metaflow_entry(run) -> dict:
    data = run.data
    return registry_entry_from_artifact(
        run_id=str(run.id),
        successful=bool(run.successful),
        model_blob=getattr(data, "model_blob", None),
        model_metadata=getattr(data, "model_metadata", {}),
        registry_record=getattr(data, "registry_record", {}),
    )


def build_metaflow_registry(flow_name="BengaluruQueueModelFlow"):
    """List model artifacts from successful runs of the current Metaflow flow."""
    from metaflow import Flow

    entries = [metaflow_entry(run) for run in Flow(flow_name)]
    return sorted(entries, key=lambda entry: entry["run_id"])


def export_metaflow_model(flow_name: str, run_id: str, destination: Path) -> dict:
    """Export only a successful, hash-verified, validation-approved run artifact."""
    run = get_metaflow_run(flow_name, run_id)
    entry = metaflow_entry(run)
    if not entry["eligible_for_promotion"]:
        raise ValueError("Metaflow run is not eligible: model, validation gate, or hash check failed")

    model_blob = run.data.model_blob
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(model_blob)
        actual_hash = hashlib.sha256(temporary_path.read_bytes()).hexdigest()
        if actual_hash != entry["model_sha256"]:
            raise ValueError("Exported Metaflow model failed its SHA-256 check")
        os.replace(temporary_path, destination)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return {**entry, "exported_path": str(destination)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flow", default="BengaluruQueueModelFlow", help="Metaflow flow name")
    parser.add_argument("--run-id", help="Export this successful Metaflow run")
    parser.add_argument("--export-model", type=Path, help="Destination path for a verified model binary")
    args = parser.parse_args()

    if args.export_model:
        if not args.run_id:
            parser.error("--export-model requires --run-id")
        print(json.dumps(export_metaflow_model(args.flow, args.run_id, args.export_model), indent=2))
        return
    if args.run_id:
        from metaflow import Run

        entries = [metaflow_entry(get_metaflow_run(args.flow, args.run_id))]
    else:
        entries = build_metaflow_registry(args.flow)
    print(json.dumps(entries, indent=2))


if __name__ == "__main__":
    main()
