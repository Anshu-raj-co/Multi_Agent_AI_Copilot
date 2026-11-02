"""The Compose project label is set in one place (scripts/_compose.sh, `docker compose -p`) and checked in others
(config/safety.json -> safety controller, kill switch fallback, tests). They must all agree, or every fault is refused."""
from __future__ import annotations

import json
import re

import pytest

from multiagent_copilot.config import REPO_ROOT, load_safety_config

LABEL = "multiagent-copilot"
OLD_LABEL = "resiliencepilot-sdv"

# file -> regex whose group(1) is the label value as that file uses it
LABEL_SITES = {
    "scripts/_compose.sh": r'^[A-Z_]*PROJECT="([^"]+)"',
    "scripts/kill-switch.sh": r'PROJECT="([^"]+)"',
    "scripts/demo-day1.sh": r"label=com\.docker\.compose\.project=([\w-]+)",
    "backend/tests/helpers.py": r'^PROJECT = "([^"]+)"',
    "backend/tests/test_discover.py": r'^PROJECT = "([^"]+)"',
    "backend/tests/test_live.py": r'st\.project == "([^"]+)"',
}


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def test_safety_config_is_the_new_label():
    assert json.loads(_read("config/safety.json"))["compose_project"] == LABEL
    assert load_safety_config().compose_project == LABEL


@pytest.mark.parametrize("rel", sorted(LABEL_SITES))
def test_every_label_copy_is_identical(rel):
    found = re.findall(LABEL_SITES[rel], _read(rel), flags=re.M)
    assert found, f"no label found in {rel}"
    assert set(found) == {LABEL}, f"{rel} uses {sorted(set(found))}"


def test_no_functional_file_keeps_the_old_label():
    roots = ["backend/multiagent_copilot", "backend/tests", "scripts", "config", "contracts"]
    offenders = []
    for root in roots:
        for p in (REPO_ROOT / root).rglob("*"):
            if p.is_file() and p.suffix in {".py", ".sh", ".json", ".yaml", ".toml", ".html"} and "__pycache__" not in p.parts:
                if p.name != "test_label_consistency.py" and OLD_LABEL in p.read_text(encoding="utf-8", errors="replace"):
                    offenders.append(p.relative_to(REPO_ROOT).as_posix())
    assert offenders == []


def test_kill_switch_reads_safety_config_and_falls_back_to_the_new_label():
    ks = _read("scripts/kill-switch.sh")
    assert 'cfg["compose_project"]' in ks and '"safety.json"' in ks          # primary: same source as the controller
    assert f'PROJECT="{LABEL}"' in ks and OLD_LABEL not in ks                # fallback literal
    assert '{{index .Config.Labels "com.docker.compose.project"}}' in ks      # it compares the label before acting


def test_compose_invocation_sets_the_label_and_its_files_exist():
    sh = _read("scripts/_compose.sh")
    var = re.search(r'^([A-Z_]*PROJECT)="([^"]+)"', sh, flags=re.M)
    assert var and var.group(2) == LABEL
    assert f'-p "${var.group(1)}"' in sh
    for f in re.findall(r'-f "\$[A-Z_]*ROOT/([^"]+)"', sh):
        assert (REPO_ROOT / f).is_file(), f"compose file missing: {f}"
