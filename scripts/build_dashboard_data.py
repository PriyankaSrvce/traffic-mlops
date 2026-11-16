"""Build src/api/dashboard/dashboard_data.json from the project's versioned reports.

The dashboard only shows numbers that exist in these files; nothing is typed in by hand
except the descriptive text of pipeline stages and governance controls.

Inputs (defaults):
  reports/phase3_drift/drift_report.json          drift detection output
  registry/model_versions.json                    model version registry
  reports/phase3_drift/promotion_comparison.json  v1 vs v2 comparison (optional)
  reports/phase3_drift/evidently_summary.json     Evidently drift scores (optional)
  reports/phase3_drift/retraining_request.json    retraining trigger decision (optional)
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "PriyankaSrvce/traffic-mlops"

BATCH_TEXT = {
    "normal_test": ("Normal (held-out)", "Held-out test runs, same demand range as training"),
    "normal_validation": ("Normal (balanced mix)", "Held-out run with the same balanced vehicle mix as the surge runs (matched control)"),
    "surge_600": ("Surge 600 veh/h", "Unseen rush-hour demand, 11 % above training maximum"),
    "surge_720": ("Surge 720 veh/h", "Unseen severe demand surge"),
    "sensor_fault_kmh": ("Sensor fault", "Synthetic: speed sensor reports km/h instead of m/s"),
}
EVAL_TEXT = {
    "original_test": "Original test (normal demand)",
    "surge_test": "Surge test seeds (123, 31415)",
    "surge_600_unseen": "Unseen surge 600 (seeds 777, 888)",
    "surge_720_unseen": "Unseen surge 720 (seeds 777, 888)",
}

PIPELINE = [
    {"stage": "Digital twin", "tool": "SUMO 1.28 + OSM Bengaluru", "status": "verified",
     "detail": "Simulated corridor, 35 signals; seeded low/medium/high demand runs"},
    {"stage": "Data & labels", "tool": "Python, DVC", "status": "verified",
     "detail": "Queue now → queue in 60 s; incident quarantine; dataset SHA-256"},
    {"stage": "Training pipeline", "tool": "Metaflow", "status": "verified",
     "detail": "start → train_evaluate → acceptance → end, artifacts per run"},
    {"stage": "Quality gate", "tool": "Metaflow acceptance step", "status": "verified",
     "detail": "≥5 % better MAE than persistence, RMSE not worse (val + test)"},
    {"stage": "Model registry", "tool": "SHA-256 registry", "status": "verified",
     "detail": "Every version, its run, dataset and stage; rollback target kept"},
    {"stage": "CI", "tool": "GitHub Actions", "status": "verified",
     "detail": "Tests, Metaflow graph checks, Docker build on every push/PR"},
    {"stage": "Deployment", "tool": "Docker → Render", "status": "manual gate",
     "detail": "Manual approval; container verifies model hash before serving"},
    {"stage": "Serving", "tool": "FastAPI + Python logging", "status": "verified",
     "detail": "/predict, /feedback, /model-info, /health; every prediction is logged"},
    {"stage": "Monitoring", "tool": "Evidently, Prometheus, Grafana", "status": "verified",
     "detail": "Evidently + PSI drift reports per batch; live /metrics charted in Grafana"},
    {"stage": "Retraining trigger", "tool": "retraining_trigger.py", "status": "verified",
     "detail": "Performance alert starts the Metaflow flow automatically"},
]
LOOP = ("Feedback loop: a performance-drift alert triggers retraining on refreshed SUMO data through the same "
        "Metaflow flow and quality gate. The new version is compared with production before a human approves deployment.")

GOVERNANCE = [
    {"area": "Model identity", "control": "Model = SHA-256 of its bytes; API refuses mismatched files",
     "evidence": "/api/v1/model-info, QUEUE_MODEL_SHA256", "why": "Same file name can hide different bytes; hash makes the live model provable"},
    {"area": "Versioning", "control": "Append-only registry with stage + reason for every version",
     "evidence": "registry/model_versions.json", "why": "Reproducibility, audit trail, safe rollback, no cherry-picking"},
    {"area": "Quality gate", "control": "4 automatic checks vs persistence baseline",
     "evidence": "Metaflow acceptance step", "why": "A model that cannot beat a free baseline adds risk without benefit"},
    {"area": "Promotion", "control": "No regression on original test + improves on drift sets + human approval",
     "evidence": "scripts/model_promotion.py, deploy job", "why": "Fixing drift must not break normal conditions; separation of duties"},
    {"area": "Data lineage", "control": "DVC + dataset SHA-256; split by whole simulation seed",
     "evidence": "*.dvc, dataset_sha256", "why": "Exact data behind every result; no leakage between train and test"},
    {"area": "Monitoring", "control": "Evidently + PSI (all rows + occupied lanes), MAE vs approved, schema checks",
     "evidence": "reports/phase3_drift/drift_report.json, evidently_summary.json", "why": "Detects decay before it causes harm; 97 % zero rows hide drift otherwise"},
    {"area": "Observability", "control": "Python logging of every prediction; Prometheus /metrics; Grafana dashboard",
     "evidence": "src/api/app.py, monitoring/", "why": "Failures and unusual inputs are visible while they happen, with an audit trail"},
    {"area": "Feedback loop", "control": "Ground-truth feedback endpoint; automatic retraining trigger with a written decision",
     "evidence": "scripts/retraining_trigger.py, retraining_request.json", "why": "Retraining starts for a recorded reason, not by someone's guess"},
    {"area": "Response policy", "control": "Performance alert → retrain; data-only alert → investigate pipeline",
     "evidence": "drift_detection.py", "why": "Retraining on a faulty sensor feed would bake the fault into the model"},
    {"area": "Change control", "control": "PR review, CI tests, manual deploy job, auto-deploy off",
     "evidence": ".github/workflows/phase2-ci.yml, render.yaml", "why": "No unreviewed or untested change reaches users"},
    {"area": "Security", "control": "Secrets outside git, non-root container, hash check before unpickling",
     "evidence": ".gitignore, Dockerfile, app.py", "why": "Pickle files can run code; leaked tokens compromise storage"},
    {"area": "Responsible claims", "control": "Simulation-only scope stated; no claim predictive beats fixed-time",
     "evidence": "docs/MODEL_CARD.md", "why": "Results from assumed demand must not be presented as field-validated"},
]

SAMPLE_REQUEST = {"queue_length_m": 4.5, "vehicle_count": 1, "halting_vehicle_count": 1, "mean_speed_mps": 0.0,
                  "phase_elapsed_s": 0.0, "intersection_id": "joinedS_11260122967_11260122969_12067305543_12067305544_#3more",
                  "approach_id": "1110163659#0", "lane_id": "1110163659#0_0", "signal_phase_id": "5",
                  "signal_state": "rrrrrrryyyrrrrrrrrrrrr", "vehicle_composition": "balanced_assumed"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--drift-report", type=Path, default=ROOT / "reports/phase3_drift/drift_report.json")
    ap.add_argument("--registry", type=Path, default=ROOT / "registry/model_versions.json")
    ap.add_argument("--comparison", type=Path, default=ROOT / "reports/phase3_drift/promotion_comparison.json")
    ap.add_argument("--evidently", type=Path, default=ROOT / "reports/phase3_drift/evidently_summary.json")
    ap.add_argument("--trigger", type=Path, default=ROOT / "reports/phase3_drift/retraining_request.json")
    ap.add_argument("--tests", type=int, required=True, help="number of unit tests in the last verified run")
    ap.add_argument("--output", type=Path, default=ROOT / "src/api/dashboard/dashboard_data.json")
    a = ap.parse_args()

    drift = json.loads(a.drift_report.read_text(encoding="utf-8"))
    registry = json.loads(a.registry.read_text(encoding="utf-8"))
    batches = []
    for b in drift["batches"]:
        label, desc = BATCH_TEXT.get(b["batch"], (b["batch"], ""))
        batches.append({"batch": b["batch"], "label": label, "description": desc, "rows": b["rows"],
                        "worst_feature": b["worst_feature"], "worst_psi": b["feature_psi"][b["worst_feature"]],
                        "model_mae": b["model_metrics"]["mae_m"], "persistence_mae": b["persistence_metrics"]["mae_m"],
                        "mae_change_vs_approved": b["mae_change_vs_approved"], "data_drift_level": b["data_drift_level"],
                        "performance_drift_level": b["performance_drift_level"], "action": b["action"], "alerts": b["alerts"]})

    prod = next(v for v in registry["versions"] if v["stage"] == "production")
    retraining = {"summary": "Retraining has not been run yet.", "models": [], "rows": []}
    if a.comparison.exists():
        cmp = json.loads(a.comparison.read_text(encoding="utf-8"))
        cand = next(v for v in registry["versions"] if v["sha256"] == cmp["candidate_sha256"])
        retraining = {
            "summary": (f"Candidate {cand['name']} ({cmp['candidate_sha256'][:8]}) vs production {prod['name']} "
                        f"({cmp['production_sha256'][:8]}) on identical evaluation sets. Decision: {cmp['decision']}."),
            "models": [f"{prod['name']} ({cmp['production_sha256'][:8]})", f"{cand['name']} ({cmp['candidate_sha256'][:8]})"],
            "rows": [{"label": EVAL_TEXT.get(k, k), "mae": [r["production_mae_m"], r["candidate_mae_m"]],
                      "persistence": r["persistence_mae_m"]} for k, r in cmp["evaluation"].items()],
            "checks": cmp["checks"], "decision": cmp["decision"]}

    evidently = None
    if a.evidently.exists():
        ev = json.loads(a.evidently.read_text(encoding="utf-8"))
        evidently = {"tool": ev["tool"], "reference": ev["reference"], "batches": [
            {"batch": name, "label": BATCH_TEXT.get(name, (name, ""))[0],
             "all_rows_drifted": b["all_rows"]["drifted_column_names"],
             "occupied_drifted": b["occupied_lanes"]["drifted_column_names"],
             "occupied_scores": {c: round(v["score"], 3) for c, v in b["occupied_lanes"]["columns"].items() if v["drift_detected"]},
             "mae_m": b["all_rows"]["model_quality"]["mae_m"],
             "report": f"/reports/evidently/{name}_occupied_lanes"} for name, b in ev["batches"].items()]}
    trigger = json.loads(a.trigger.read_text(encoding="utf-8")) if a.trigger.exists() else None

    data = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "performance": {"test_mae": prod["test_mae"], "persistence_test_mae": prod["persistence_test_mae"],
                        "improvement_pct": round((1 - prod["test_mae"] / prod["persistence_test_mae"]) * 100),
                        "rows": prod["training_rows"], "runs": prod["training_runs"]},
        "quality": {"tests": a.tests},
        "pipeline": PIPELINE, "pipeline_loop": LOOP,
        "drift": {"policy": drift["policy"], "approved_test_mae_m": drift["approved_test_mae_m"],
                  "model_sha256": drift["model_sha256"], "generated_utc": drift["generated_utc"], "batches": batches},
        "evidently": evidently, "retraining_trigger": trigger,
        "versions": registry["versions"], "retraining": retraining, "governance": GOVERNANCE,
        "sample_request": SAMPLE_REQUEST,
        "links": {"repo": f"https://github.com/{REPO}", "repo_slug": REPO,
                  "governance": f"https://github.com/{REPO}/blob/main/docs/GOVERNANCE.md"},
        "limitations": "simulated demand on one OSM corridor; not field-validated; drift batches are SUMO scenarios and one synthetic sensor fault",
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {a.output}")


if __name__ == "__main__":
    main()
