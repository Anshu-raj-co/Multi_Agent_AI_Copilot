"""`mcop team run | sessions | show`: the approval gate cannot be skipped from the CLI."""
from __future__ import annotations

import json

import pytest

import multiagent_copilot.__main__ as cli
from multiagent_copilot.config import load_experiment_catalog
from multiagent_copilot.evidence import EvidenceStore
from multiagent_copilot.orchestrator import ExperimentRunner
from multiagent_copilot.safety import SafetyController

from helpers import FakeDocker, FakeObserver, FakeWorld, make_config

FAULT_CALLS = {"pause", "unpause", "stop", "start"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    cfg = make_config(tmp_path, max_duration_s=2)
    catalog = load_experiment_catalog()
    world = FakeWorld()
    docker, observer = FakeDocker(world), FakeObserver(world)
    ctl = SafetyController(cfg, catalog, docker, observer=observer)
    store = EvidenceStore(cfg.data_dir)
    store.save_baseline("baseline-20261102T000000Z", {"summary": {"latency_ms": {"p95": 5.0}}})
    runner = ExperimentRunner(cfg, catalog, ctl, docker, observer, store)
    monkeypatch.setattr(cli, "build", lambda on_event=None: (cfg, catalog, docker, ctl, observer, store, runner))
    monkeypatch.setattr(cli, "_team_dirs", lambda: (cfg.data_dir / "team_sessions", tmp_path / "committed"))
    monkeypatch.setattr(cli.signal, "signal", lambda *a: None)       # pytest owns SIGINT
    return cfg, world


def answers(monkeypatch, *replies):
    it = iter(replies)
    asked = []

    def fake_input(prompt=""):
        asked.append(prompt)
        try:
            return next(it)
        except StopIteration:
            raise EOFError
    monkeypatch.setattr("builtins.input", fake_input)
    return asked


def faults(world) -> list[str]:
    return [c[1] for c in world.calls if c[1] in FAULT_CALLS]


def sessions(cfg) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((cfg.data_dir / "team_sessions").glob("*.json"))]


@pytest.mark.parametrize("argv, replies", [
    (["team", "run"], ["telemetry_stall", "Anshu", "no"]),
    (["team", "run"], ["telemetry_stall", "Anshu", "approve"]),                      # case matters
    (["team", "run", "--experiment", "telemetry_stall"], ["Anshu", "yes"]),          # one flag is not enough
    (["team", "run", "--approved-by", "Anshu"], ["telemetry_stall", ""]),
    (["team", "run"], ["99"]),                                                        # not a proposal
    (["team", "run"], []),                                                            # EOF: no terminal
    (["team", "run"], ["telemetry_stall", "   ", "APPROVE"]),                         # blank name
])
def test_interactive_gate_without_a_typed_approve_executes_nothing(env, monkeypatch, capsys, argv, replies):
    cfg, world = env
    answers(monkeypatch, *replies)
    assert cli.main(argv) == 2
    assert faults(world) == []
    (s,) = sessions(cfg)
    assert s["outcome"] == "refused" and s["approval"] is None and s["run_id"] is None
    out = capsys.readouterr().out
    assert "nothing executed" in out or "not approved" in out


def test_interactive_approval_runs_one_session(env, monkeypatch, capsys):
    cfg, world = env
    asked = answers(monkeypatch, "telemetry_stall", "Anshu", "APPROVE")
    assert cli.main(["team", "run"]) == 0
    assert any("APPROVE" in a for a in asked) and "pause" in faults(world)
    (s,) = sessions(cfg)
    assert s["outcome"] == "completed" and s["approval"]["approved_by"] == "Anshu"


def test_non_interactive_only_with_both_flags_and_live_lines_in_order(env, monkeypatch, capsys):
    cfg, world = env
    monkeypatch.setattr("builtins.input", lambda *_: pytest.fail("non-interactive run must not prompt"))
    assert cli.main(["team", "run", "--experiment", "telemetry_stall", "--approved-by", "Anshu", "--no-ai"]) == 0
    out = capsys.readouterr().out
    marks = [out.index(m) for m in ("[Monitor]", "[Planner]", "[HUMAN]", "[Executor]", "[Analyst]")]
    assert marks == sorted(marks)
    (s,) = sessions(cfg)
    assert s["outcome"] == "completed" and s["approval"]["approved_by"] == "Anshu"


def test_unknown_experiment_is_refused_before_the_gate(env, monkeypatch):
    cfg, world = env
    monkeypatch.setattr("builtins.input", lambda *_: pytest.fail("must not reach the gate"))
    assert cli.main(["team", "run", "--experiment", "nope", "--approved-by", "Anshu"]) == 2
    assert faults(world) == [] and sessions(cfg)[0]["steps"][-1]["status"] == "refused"


@pytest.mark.parametrize("flag", ["--yes", "--skip-approval", "--force", "--auto-approve"])
def test_no_flag_skips_approval(env, flag):
    with pytest.raises(SystemExit):
        cli.main(["team", "run", flag])


def test_sessions_and_show(env, monkeypatch, capsys):
    cfg, _ = env
    assert cli.main(["team", "sessions"]) == 0
    assert "No team sessions yet. Run: mcop team run" in capsys.readouterr().out
    monkeypatch.setattr("builtins.input", lambda *_: pytest.fail("no prompt"))
    cli.main(["team", "run", "--experiment", "telemetry_stall", "--approved-by", "Anshu"])
    cli.main(["team", "run", "--experiment", "telemetry_stall", "--approved-by", "Anshu"])
    capsys.readouterr()
    assert cli.main(["team", "sessions"]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    ids = [line.split()[0] for line in lines]
    assert len(ids) == 2 and ids == sorted(ids, reverse=True)                      # newest first
    assert cli.main(["team", "show", ids[0]]) == 0
    shown = capsys.readouterr().out
    assert "[HUMAN] approved by Anshu" in shown and "[Executor]" in shown and "deterministic" in shown
    assert cli.main(["team", "show", "../../etc/passwd"]) == 2
    assert cli.main(["team", "show", "20200101T000000Z-000000"]) == 1


def test_read_only_team_commands_build_no_safety_objects(env, monkeypatch, capsys):
    monkeypatch.setattr(cli, "build", lambda *_: pytest.fail("safety objects built"))
    assert cli.main(["team", "sessions"]) == 0
