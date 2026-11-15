"""Model versioning: compare a candidate with production, record the decision, roll back.

Phase 3. The registry (registry/model_versions.json) is the single list of every model
version, identified by the SHA-256 of its bytes. This tool:

  compare   scores production and candidate on the same evaluation sets and applies the
            promotion policy below; writes a JSON comparison report.
  rollback  prints the exact deployment settings that restore the previous approved version.

Promotion policy (all must hold):
  P1  candidate passed the Metaflow quality gate (4 conditions vs persistence)
  P2  no regression on the original held-out test set: MAE <= production MAE x 1.02
  P3  on every drift evaluation set, candidate MAE < production MAE (it fixes the drift)
  P4  a human approves the deployment (the registry stage only becomes "production"
      after the deploy is done and the live API reports the new SHA-256)

Models are only deserialized after their SHA-256 matches the expected value.

Usage:
  python scripts/model_promotion.py compare --production PATH:SHA --candidate PATH:SHA \
      --gate-passed --set original_test=test.csv --drift-set surge_600=a.csv ... --output cmp.json
  python scripts/model_promotion.py rollback --registry registry/model_versions.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sumo" / "bengaluru_osm"))

FEATURES = ["queue_length_m", "vehicle_count", "halting_vehicle_count", "mean_speed_mps", "phase_elapsed_s",
            "intersection_id", "approach_id", "lane_id", "signal_phase_id", "signal_state", "vehicle_composition"]
TARGET = "queue_length_m_t_plus_60s"
REGRESSION_TOLERANCE = 1.02


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_pinned(spec: str):
    import joblib
    from bengaluru_model import HurdleQueueModel  # noqa: F401  (unpickling)

    path, _, expected = spec.rpartition(":")
    if len(expected) != 64:
        raise SystemExit(f"Expected PATH:SHA256, got {spec!r}")
    digest = sha256(Path(path))
    if digest != expected:
        raise SystemExit(f"SHA-256 mismatch for {path}: {digest[:12]} != {expected[:12]}")
    return joblib.load(path), digest


def mae_table(models: dict, sets: dict) -> dict:
    import numpy as np
    import pandas as pd

    out = {}
    for name, path in sets.items():
        frame = pd.read_csv(path)
        x = frame[FEATURES].copy()
        for c in FEATURES[5:]:
            x[c] = x[c].astype(str)
        y = frame[TARGET].to_numpy(float)
        row = {"rows": int(len(frame)), "persistence_mae_m": float(np.mean(np.abs(frame["queue_length_m"].to_numpy(float) - y)))}
        for label, model in models.items():
            row[f"{label}_mae_m"] = float(np.mean(np.abs(model.predict(x) - y)))
        out[name] = row
    return out


def decide(table: dict, base_sets: list[str], drift_sets: list[str], gate_passed: bool) -> dict:
    checks = {"P1_candidate_passed_quality_gate": bool(gate_passed)}
    for s in base_sets:
        checks[f"P2_no_regression_{s}"] = table[s]["candidate_mae_m"] <= table[s]["production_mae_m"] * REGRESSION_TOLERANCE
    for s in drift_sets:
        checks[f"P3_improves_{s}"] = table[s]["candidate_mae_m"] < table[s]["production_mae_m"]
    ok = all(checks.values())
    return {"checks": checks,
            "decision": "APPROVED_FOR_PROMOTION (awaiting human deployment approval, P4)" if ok else "REJECTED",
            "promote": ok}


def cmd_compare(a) -> None:
    prod, prod_sha = load_pinned(a.production)
    cand, cand_sha = load_pinned(a.candidate)
    sets = dict(s.split("=", 1) for s in a.set)
    drift = dict(s.split("=", 1) for s in a.drift_set)
    table = mae_table({"production": prod, "candidate": cand}, {**sets, **drift})
    result = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "production_sha256": prod_sha, "candidate_sha256": cand_sha,
              "policy": {"regression_tolerance": REGRESSION_TOLERANCE}, "evaluation": table,
              **decide(table, list(sets), list(drift), a.gate_passed)}
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    Path(a.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    for name, row in table.items():
        print(f"{name:>22}: production {row['production_mae_m']:.4f}  candidate {row['candidate_mae_m']:.4f}  "
              f"persistence {row['persistence_mae_m']:.4f}  (rows {row['rows']})")
    for k, v in result["checks"].items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    print("DECISION:", result["decision"])


def cmd_rollback(a) -> None:
    reg = json.loads(Path(a.registry).read_text(encoding="utf-8"))
    current = next((v for v in reg["versions"] if v["stage"] == "production"), None)
    previous = [v for v in reg["versions"] if v.get("rollback_target") and v is not current]
    if not previous:
        print(f"Current production: {current['name'] if current else 'none'}. No earlier approved version to roll back to;"
              " rollback becomes available after the next promotion archives this one.")
        return
    target = previous[-1]
    print(f"Current production: {current['name'] if current else 'none'} ({current['sha256'][:12] if current else '-'})")
    print(f"Roll back to:       {target['name']} ({target['sha256'][:12]})")
    print("Set these on the Render service, then redeploy (CI 'deploy' job or Render dashboard):")
    print(f"  QUEUE_MODEL_URL    = {target.get('artifact_url', '<release asset URL for this SHA>')}")
    print(f"  QUEUE_MODEL_SHA256 = {target['sha256']}")
    print("The container refuses to start if the downloaded bytes do not match, so a wrong URL cannot go live.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compare")
    c.add_argument("--production", required=True, help="PATH:SHA256")
    c.add_argument("--candidate", required=True, help="PATH:SHA256")
    c.add_argument("--gate-passed", action="store_true", help="candidate passed the Metaflow acceptance step")
    c.add_argument("--set", action="append", default=[], help="NAME=csv, regression check (P2)")
    c.add_argument("--drift-set", action="append", default=[], help="NAME=csv, must improve (P3)")
    c.add_argument("--output", required=True)
    r = sub.add_parser("rollback")
    r.add_argument("--registry", default=str(ROOT / "registry" / "model_versions.json"))
    a = ap.parse_args()
    {"compare": cmd_compare, "rollback": cmd_rollback}[a.cmd](a)


if __name__ == "__main__":
    main()
