"""Automatic retraining trigger: turn a drift report into a retraining decision and run it.

Phase 3 feedback loop. Reads the drift report written by drift_detection.py and applies
the governance policy (docs/GOVERNANCE.md, section 5):

  performance ALERT on any batch          -> TRIGGER retraining
  data ALERT only (accuracy still fine)   -> NO retraining; open a data-pipeline investigation
  otherwise                               -> NO retraining

Every decision is written to a JSON request file and logged, so there is an audit trail of
why a retraining run was (or was not) started. With --execute the trigger launches the
Metaflow training flow on the refreshed dataset; the flow's own quality gate and
scripts/model_promotion.py still decide whether the new model may replace production.

Exit code: 0 = no retraining needed, 10 = retraining triggered (useful for schedulers/CI).

Usage:
  python scripts/retraining_trigger.py --drift-report reports/phase3_drift/drift_report.json
  python scripts/retraining_trigger.py --drift-report ... --execute --dataset refreshed.csv
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW = ROOT / "flows" / "bengaluru_queue_model_flow.py"
LOGGER = logging.getLogger("retraining_trigger")
EXIT_TRIGGERED = 10


def decide(report: dict) -> dict:
    """Apply the trigger policy to a drift report. Pure function (unit tested)."""
    performance = [b["batch"] for b in report["batches"] if b["performance_drift_level"] == "ALERT"]
    data_only = [b["batch"] for b in report["batches"]
                 if b["data_drift_level"] == "ALERT" and b["performance_drift_level"] != "ALERT"]
    reasons = [alert for b in report["batches"] if b["batch"] in performance for alert in b["alerts"]]
    return {
        "retrain": bool(performance),
        "decision": "TRIGGER_RETRAINING" if performance else "NO_RETRAINING",
        "performance_alert_batches": performance,
        "pipeline_investigation_batches": data_only,
        "reasons": reasons,
        "production_model_sha256": report.get("model_sha256"),
        "drift_report_generated_utc": report.get("generated_utc"),
    }


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def launch_flow(dataset: Path, artifact_root: Path, flow_args: list[str]) -> int:
    cmd = [sys.executable, str(FLOW), *flow_args, "run", "--dataset", str(dataset), "--artifact-root", str(artifact_root)]
    LOGGER.info("launching_metaflow flow=%s dataset=%s", FLOW.name, dataset.name)
    return subprocess.run(cmd, cwd=ROOT).returncode


def newest_candidate(artifact_root: Path) -> dict | None:
    """Read the evaluation report of the run the flow just wrote (newest timestamped folder)."""
    reports = sorted(artifact_root.glob("*/evaluation/report.json"))
    if not reports:
        return None
    report = json.loads(reports[-1].read_text(encoding="utf-8"))
    return {"model_version": report["model_version"], "model_sha256": report["model_sha256"],
            "validation_status": report["validation_status"], "acceptance_gate": report["acceptance_gate"],
            "test_mae_m": report["test"]["mae_m"], "run_folder": reports[-1].parents[1].name}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--drift-report", type=Path, default=ROOT / "reports/phase3_drift/drift_report.json")
    ap.add_argument("--request-file", type=Path, default=None, help="where to write the decision (default: next to the report)")
    ap.add_argument("--execute", action="store_true", help="actually launch the Metaflow training flow when triggered")
    ap.add_argument("--dataset", type=Path, help="refreshed training dataset (required with --execute)")
    ap.add_argument("--artifact-root", type=Path, default=ROOT / "reports/metaflow/bengaluru")
    ap.add_argument("--flow-arg", action="append", default=[], help="extra Metaflow option, e.g. --flow-arg=--metadata=service")
    ap.add_argument("--log-file", type=Path, default=None)
    a = ap.parse_args()

    handlers = [logging.StreamHandler()]
    if a.log_file:
        a.log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(a.log_file, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s", handlers=handlers)

    report = json.loads(a.drift_report.read_text(encoding="utf-8"))
    decision = decide(report)
    decision.update(evaluated_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    drift_report=a.drift_report.name, executed=False)
    for batch in decision["pipeline_investigation_batches"]:
        LOGGER.warning("pipeline_investigation batch=%s detail=data_alert_without_accuracy_loss_do_not_retrain", batch)
    if not decision["retrain"]:
        LOGGER.info("decision=NO_RETRAINING batches_checked=%d", len(report["batches"]))
    else:
        LOGGER.warning("decision=TRIGGER_RETRAINING batches=%s", ",".join(decision["performance_alert_batches"]))
        for reason in decision["reasons"]:
            LOGGER.warning("reason=%s", reason)
        if a.execute:
            if not a.dataset or not a.dataset.is_file():
                LOGGER.error("execute_refused detail=--dataset_must_point_to_the_refreshed_training_data")
                return 2
            decision["dataset"] = {"file": a.dataset.name, "sha256": sha256(a.dataset)}
            code = launch_flow(a.dataset, a.artifact_root, a.flow_arg)
            decision.update(executed=True, metaflow_exit_code=code,
                            next_step="scripts/model_promotion.py compare (promotion checks P1-P3), then human approval")
            if code:
                LOGGER.error("retraining_failed metaflow_exit_code=%d", code)
            else:
                decision["candidate"] = newest_candidate(a.artifact_root)
                LOGGER.info("retraining_finished candidate_sha256=%s detail=candidate_must_still_pass_promotion_checks",
                            (decision["candidate"] or {}).get("model_sha256"))
        else:
            LOGGER.info("dry_run detail=pass_--execute_and_--dataset_to_launch_the_metaflow_flow")

    request_file = a.request_file or a.drift_report.with_name("retraining_request.json")
    request_file.write_text(json.dumps(decision, indent=2), encoding="utf-8")
    LOGGER.info("request_file=%s", request_file.name)
    if decision.get("metaflow_exit_code"):
        return 1
    return EXIT_TRIGGERED if decision["retrain"] else 0


if __name__ == "__main__":
    sys.exit(main())
