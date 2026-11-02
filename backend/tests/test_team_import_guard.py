"""Separation inside agent_team/, checked statically (same AST technique as the ai.py guard in test_ai.py) and by
importing modules in a fresh interpreter: only the Safety Executor reaches the safety controller and orchestrator,
and it can never reach the AI client."""
from __future__ import annotations

import ast
import subprocess
import sys

import pytest

from multiagent_copilot.config import REPO_ROOT

PKG = REPO_ROOT / "backend" / "multiagent_copilot" / "agent_team"
SAFETY_MODULES = {"orchestrator", "safety", "faults", "docker_cli", "guardrails"}


def imports(name: str) -> dict[str, set[str]]:
    """{'parent': modules of multiagent_copilot, 'sibling': agent_team modules, 'absolute': third-party/stdlib}."""
    tree = ast.parse((PKG / f"{name}.py").read_text(encoding="utf-8"))
    out = {"parent": set(), "sibling": set(), "absolute": set()}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out["absolute"] |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level == 0:
                out["absolute"].add(mod)
            elif node.level == 1:
                out["sibling"] |= {mod} if mod else {a.name for a in node.names}
            else:
                out["parent"] |= {mod.split(".")[0]} if mod else {a.name for a in node.names}
    return out


def names_used(name: str) -> set[str]:
    tree = ast.parse((PKG / f"{name}.py").read_text(encoding="utf-8"))
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | \
           {f"{n.value.id}.{n.attr}" for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}


def test_package_init_imports_nothing():
    assert imports("__init__") == {"parent": set(), "sibling": set(), "absolute": set()}


def test_agents_cannot_reach_safety_orchestrator_faults_docker_or_a_shell():
    imp = imports("agents")
    assert not imp["parent"] & SAFETY_MODULES, imp["parent"]
    assert imp["parent"] <= {"observation", "telemetry", "baseline", "planner", "ai", "scoring", "findings"}
    assert imp["sibling"] <= {"trace"}
    assert not imp["absolute"] & {"subprocess", "os", "shutil", "socket"}
    assert not {"os.system", "subprocess"} & names_used("agents")


def test_executor_is_the_only_bridge_to_safety_and_never_reaches_the_ai():
    imp = imports("executor_agent")
    assert imp["parent"] <= {"orchestrator", "safety", "config"}
    assert imp["sibling"] <= {"trace"}                                  # not agents: no path to ai.py
    assert not (imp["parent"] | imp["absolute"]) & {"ai", "httpx", "requests", "ollama"}
    assert not {i for i in imp["absolute"] if "ollama" in i.lower() or i in ("httpx", "requests", "urllib.request")}


def test_pipeline_only_coordinates_the_agents():
    imp = imports("pipeline")
    assert imp["parent"] == set(), imp["parent"]                       # no direct path to safety, faults, ai, ...
    assert imp["sibling"] <= {"agents", "executor_agent", "trace"}
    assert not imp["absolute"] & {"subprocess", "httpx", "requests"}


@pytest.mark.parametrize("name", ["__init__", "agents", "pipeline", "trace"])
def test_no_other_team_module_imports_the_safety_side(name):
    assert not imports(name)["parent"] & SAFETY_MODULES


def _loaded_after_import(module: str) -> set[str]:
    code = (f"import sys, {module}; "
            "print('\\n'.join(m for m in sys.modules if m.startswith('multiagent_copilot') or m in ('httpx',)))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=REPO_ROOT / "backend",
                         timeout=60)
    assert out.returncode == 0, out.stderr
    return set(out.stdout.split())


def test_importing_the_executor_does_not_load_the_ai_client():
    loaded = _loaded_after_import("multiagent_copilot.agent_team.executor_agent")
    assert "multiagent_copilot.ai" not in loaded and "multiagent_copilot.agent_team.agents" not in loaded
    assert "multiagent_copilot.orchestrator" in loaded


def test_importing_the_agents_does_not_load_the_safety_side():
    loaded = _loaded_after_import("multiagent_copilot.agent_team.agents")
    assert not {f"multiagent_copilot.{m}" for m in SAFETY_MODULES} & loaded
    assert "multiagent_copilot.agent_team.executor_agent" not in loaded
