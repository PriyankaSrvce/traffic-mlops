"""Team setup stays consistent with the registry (so teammates always get the production model)."""
import json
import re
from pathlib import Path

import pytest

from scripts.fetch_model import select
from scripts.team_helpers import check_reproduced

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = json.loads((ROOT / "registry/model_versions.json").read_text(encoding="utf-8"))
PRODUCTION = next(v for v in REGISTRY["versions"] if v["stage"] == "production")


def test_monitoring_stack_downloads_the_registry_production_model():
    compose = (ROOT / "monitoring/docker-compose.yml").read_text(encoding="utf-8")
    url = re.search(r"QUEUE_MODEL_URL: \$\{QUEUE_MODEL_URL:-([^}]+)\}", compose).group(1)
    assert url == PRODUCTION["artifact_url"]
    assert f"QUEUE_MODEL_SHA256={PRODUCTION['sha256']}" in (ROOT / "Dockerfile").read_text(encoding="utf-8")


def test_fetch_model_selects_production_or_an_exact_prefix():
    assert select(REGISTRY, None)["sha256"] == PRODUCTION["sha256"]
    assert select(REGISTRY, "167b")["stage"] == "archived"
    with pytest.raises(SystemExit):
        select(REGISTRY, "")  # matches every version
    with pytest.raises(SystemExit):
        select(REGISTRY, "b46a")  # the rejected v0 was never published


def test_reproduction_check_names_registered_and_unknown_models(tmp_path, capsys):
    for i, sha in enumerate([PRODUCTION["sha256"], "f" * 64]):
        report = tmp_path / f"2026111{i}T000000Z-{i}" / "evaluation" / "report.json"
        report.parent.mkdir(parents=True)
        report.write_text(json.dumps({"model_sha256": sha}), encoding="utf-8")
    assert check_reproduced(tmp_path) == 1
    out = capsys.readouterr().out
    assert PRODUCTION["name"] in out and "NOT a registered model" in out


def test_team_scripts_keep_linux_line_endings_and_launchers_point_at_existing_scripts():
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "*.sh    text eol=lf" in attributes
    for launcher in (ROOT / "team/windows").glob("*.cmd"):
        for script in re.findall(r"team/wsl/([\w.]+\.sh)", launcher.read_text(encoding="utf-8")):
            assert (ROOT / "team/wsl" / script).is_file(), (launcher.name, script)
