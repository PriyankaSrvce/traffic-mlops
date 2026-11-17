"""Download a registered model file and verify its SHA-256 (standard library only).

The model files are not in Git. Their download addresses and fingerprints are in
registry/model_versions.json. This script downloads one of them over HTTPS and keeps it
only if its SHA-256 matches the registry.

Usage:
  python scripts/fetch_model.py                 # the current production model
  python scripts/fetch_model.py --version 167b  # any registered version, by SHA prefix

Saves to models/<first 12 SHA characters>/bengaluru_queue_hurdle_v1_2026-11.joblib
(models/ is git-ignored) and prints the path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "model_versions.json"
FILENAME = "bengaluru_queue_hurdle_v1_2026-11.joblib"


def select(registry: dict, version: str | None) -> dict:
    """Return the production entry, or the single entry whose SHA-256 starts with `version`."""
    if version is None:
        matches = [v for v in registry["versions"] if v["stage"] == "production"]
    else:
        matches = [v for v in registry["versions"] if v["sha256"].startswith(version.lower())]
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one matching model version, found {len(matches)}")
    if not matches[0].get("artifact_url"):
        raise SystemExit(f"{matches[0]['name']} has no download address in the registry (it was never published)")
    return matches[0]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download_verified(url: str, expected_sha256: str, destination: Path) -> Path:
    if not url.startswith("https://"):
        raise SystemExit("Refusing a non-HTTPS model address")
    if destination.exists() and sha256_file(destination) == expected_sha256:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "traffic-mlops-fetch/1.0"}),
                                    timeout=120) as response:
            while block := response.read(1 << 20):
                tmp.write(block)
    actual = sha256_file(tmp_path)
    if actual != expected_sha256:
        tmp_path.unlink(missing_ok=True)
        raise SystemExit(f"Downloaded file has SHA-256 {actual[:12]}, registry says {expected_sha256[:12]}; not saved")
    tmp_path.replace(destination)
    return destination


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--version", help="SHA-256 prefix of a registered version (default: production)")
    ap.add_argument("--registry", type=Path, default=REGISTRY)
    ap.add_argument("--print-test-mae", action="store_true", help="only print the selected model's approved test MAE")
    a = ap.parse_args()
    entry = select(json.loads(a.registry.read_text(encoding="utf-8")), a.version)
    if a.print_test_mae:
        print(entry["test_mae"])
        return
    path = download_verified(entry["artifact_url"], entry["sha256"], ROOT / "models" / entry["sha256"][:12] / FILENAME)
    print(f"{entry['name']} ({entry['stage']}) sha256={entry['sha256'][:12]} -> {path}", file=sys.stderr)
    print(path)


if __name__ == "__main__":
    main()
