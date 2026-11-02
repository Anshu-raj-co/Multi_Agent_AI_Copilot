"""scripts/kill-switch.sh must write EMERGENCY_STOP into the configured data dir even when the repo path has spaces.

Runs the real script from a temporary repo copy whose path contains a space, with a fake `docker` on PATH that reports
every target as running and unpaused in the sandbox project (nothing real is touched)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

import pytest

from multiagent_copilot.config import REPO_ROOT

BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(BASH is None or "system32" in BASH.lower(),
                                reason="needs a POSIX bash (Git Bash on Windows), not the WSL launcher")

FAKE_DOCKER = """#!/usr/bin/env bash
echo "$*" >> "$(dirname "$0")/docker-calls.log"
case "$*" in
  *compose.project*) echo multiagent-copilot ;;
  *"running={{.State.Running}}"*) echo "running=true paused=false" ;;
  *) echo "unexpected docker call: $*" >&2; exit 1 ;;
esac
"""


def _posix(p) -> str:
    s = str(p).replace("\\", "/")
    return f"/{s[0].lower()}{s[2:]}" if sys.platform == "win32" and s[1:2] == ":" else s


def test_emergency_stop_lands_in_data_dir_when_repo_path_has_spaces(tmp_path):
    repo = tmp_path / "repo with space"
    (repo / "scripts").mkdir(parents=True)
    (repo / "config").mkdir()
    shutil.copy(REPO_ROOT / "scripts" / "kill-switch.sh", repo / "scripts" / "kill-switch.sh")
    for f in ("safety.json", "experiments.json"):
        shutil.copy(REPO_ROOT / "config" / f, repo / "config" / f)
    fake = tmp_path / "fakebin"
    fake.mkdir()
    (fake / "docker").write_text(FAKE_DOCKER, encoding="utf-8", newline="\n")
    (fake / "python").write_text(f'#!/usr/bin/env bash\nexec "{_posix(sys.executable)}" "$@"\n', encoding="utf-8",
                                 newline="\n")
    for f in ("docker", "python"):
        os.chmod(fake / f, 0o755)
    env = {**os.environ, "PATH": str(fake) + os.pathsep + os.environ.get("PATH", "")}

    proc = subprocess.run([BASH, _posix(repo / "scripts" / "kill-switch.sh")], capture_output=True, text=True,
                          env=env, timeout=60)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (repo / "backend" / "data" / "EMERGENCY_STOP").is_file(), proc.stdout + proc.stderr
    assert "falling back" not in proc.stderr                                   # config was read, not the defaults
    assert not list(tmp_path.glob("repo/**/EMERGENCY_STOP")) and not (tmp_path / "repo").exists()
    calls = (fake / "docker-calls.log").read_text(encoding="utf-8")
    assert "fms-forwarder" in calls and "influxDB" in calls                    # every allowlisted target checked
    assert "skip" not in proc.stdout
