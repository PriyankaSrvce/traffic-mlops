"""Small helpers for the team scripts in team/wsl/ (kept in Python so the shell stays simple).

  ensure-bucket              create the "metaflow" bucket in the local S3 store if missing
  check-reproduced <folder>  compare the newest Metaflow training outputs with the registry
  dvc-targets                print the DVC pointer files (data only, no pipeline outputs)
  check-data                 compare every DVC-tracked file with the MD5 in its pointer file
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def dvc_targets() -> list[str]:
    """The *.dvc pointer files tracked by Git. Using them as explicit targets keeps DVC away from
    dvc.yaml pipeline outputs (Phase 1 model.pkl etc.), which are not stored on the remote."""
    import subprocess

    out = subprocess.run(["git", "ls-files", "*.dvc"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return sorted(out.split())


def check_data() -> int:
    import hashlib
    import re

    bad = 0
    for ptr in dvc_targets():
        text = (ROOT / ptr).read_text(encoding="utf-8")
        path = Path(ptr).parent / re.search(r"path: (.+)", text).group(1).strip()
        want = re.search(r"md5: (\w+)", text).group(1)
        if not (ROOT / path).exists():
            print(f"  missing  {path.as_posix()}")
            bad += 1
            continue
        digest = hashlib.md5()
        with (ROOT / path).open("rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                digest.update(block)
        ok = digest.hexdigest() == want
        bad += not ok
        print(f"  {'OK      ' if ok else 'CHANGED '} {path.as_posix()}")
    return 1 if bad else 0


def ensure_bucket() -> None:
    import boto3

    s3 = boto3.client("s3", endpoint_url="http://localhost:9000")
    if "metaflow" not in [b["Name"] for b in s3.list_buckets().get("Buckets", [])]:
        s3.create_bucket(Bucket="metaflow")


def check_reproduced(folder: Path, last: int = 2) -> int:
    registry = {v["sha256"]: v for v in json.loads((ROOT / "registry/model_versions.json").read_text(encoding="utf-8"))["versions"]}
    reports = sorted(folder.glob("*/evaluation/report.json"))[-last:]
    if not reports:
        print("  no training outputs found")
        return 1
    unmatched = 0
    for path in reports:
        sha = json.loads(path.read_text(encoding="utf-8"))["model_sha256"]
        entry = registry.get(sha)
        unmatched += entry is None
        label = f"{entry['name']} ({entry['stage']})" if entry else "NOT a registered model (environment differs from the pinned one?)"
        print(f"  {path.parents[1].name}: {sha[:12]} -> {label}")
    return 1 if unmatched else 0


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "ensure-bucket":
        ensure_bucket()
    elif command == "check-reproduced":
        sys.exit(check_reproduced(Path(sys.argv[2])))
    elif command == "dvc-targets":
        targets = dvc_targets()
        if not targets:
            sys.exit("No *.dvc pointer files found (run this inside the repository).")
        for target in targets:
            print(target)
    elif command == "check-data":
        sys.exit(check_data())
    else:
        sys.exit(__doc__)
