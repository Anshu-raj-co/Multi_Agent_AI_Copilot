"""Agent-team pipeline: Monitor -> Planner -> HUMAN GATE -> Safety Executor -> Analyst, on the existing fakes."""
from __future__ import annotations

import json
from datetime import timedelta
from types import SimpleNamespace

import httpx
import pytest

from multiagent_copilot.agent_team.agents import AnalystAgent, MonitorAgent, PlannerAgent
from multiagent_copilot.agent_team.executor_agent import SafetyExecutorAgent
from multiagent_copilot.agent_team.pipeline import make_approval, run_session
from multiagent_copilot.agent_team.trace import ApprovalRecord, TeamSession
from multiagent_copilot.config import ExperimentSpec
from multiagent_copilot.evidence import EvidenceStore
from multiagent_copilot.orchestrator import ExperimentRunner
from multiagent_copilot.safety import SafetyController
from multiagent_copilot.scoring import load_runs

from helpers import FakeDocker, FakeObserver, FakeWorld, make_config
from test_ai import FINDINGS, RUNS, STALL_SILENT, _item, _provider
from test_planner_findings import DEP_MAP
from test_team_trace import schema_errors

SYMPTOMS = ("createdDateTime stops advancing", "HTTP 200 continues")
RISKS = ("forwarder may drop buffered statuses",)
RAW = {"telemetry_stall": {"description": "pause the forwarder", "mechanism": "docker_pause",
                           "allowed_targets": ["fms-forwarder"], "max_duration_s": 30,
                           "expected_symptoms": list(SYMPTOMS), "risks": list(RISKS), "blast_radius": ["fms-forwarder"]}}
CATALOG = {"telemetry_stall": ExperimentSpec("telemetry_stall", "docker_pause", ("fms-forwarder",), 30,
                                             expected_symptoms=SYMPTOMS, risks=RISKS)}
FAULT_CALLS = {"pause", "unpause", "stop", "start"}


class SpyDocker:
    """Records every docker call by method name, then delegates to FakeDocker."""

    def __init__(self, inner: FakeDocker) -> None:
        self.inner, self.calls = inner, []

    def __getattr__(self, name):
        attr = getattr(self.inner, name)

        def call(*a, **kw):
            self.calls.append(name)
            return attr(*a, **kw)
        return call


class CountingRunner:
    def __init__(self, inner, fail: Exception | None = None) -> None:
        self.inner, self.fail, self.runs = inner, fail, 0

    def run(self, req):
        self.runs += 1
        if self.fail is not None:
            raise self.fail
        return self.inner.run(req)


def make_team(tmp_path, *, provider=None, baseline=True, runner_fail=None, runs_loader=None):
    cfg = make_config(tmp_path, max_duration_s=2)
    world = FakeWorld()
    docker = SpyDocker(FakeDocker(world))
    observer = FakeObserver(world)
    ctl = SafetyController(cfg, CATALOG, docker, observer=observer)
    store = EvidenceStore(cfg.data_dir)
    runner = CountingRunner(ExperimentRunner(cfg, CATALOG, ctl, docker, observer, store), runner_fail)
    runs_dir = cfg.data_dir / "runs"
    runs_loader = runs_loader or (lambda: load_runs(runs_dir) if runs_dir.is_dir() else [])
    return SimpleNamespace(
        cfg=cfg, world=world, docker=docker, ctl=ctl, runner=runner, sessions_dir=cfg.data_dir / "team_sessions",
        monitor=MonitorAgent(observer, cfg.stale_threshold_s, (lambda: ("baseline-x", {})) if baseline else (lambda: None),
                             samples=3, interval_s=0.05),
        planner=PlannerAgent(RAW, DEP_MAP, runs_loader, cfg.max_duration_s, provider=provider),
        executor=SafetyExecutorAgent(CATALOG, ctl, runner),
        analyst=AnalystAgent(runs_loader, provider=provider),
    )


class Gate:
    """Stands in for the human: approves the top proposal (or a given id) as a named person, and counts calls."""

    def __init__(self, name="Anshu", experiment_id=None, answer="approve") -> None:
        self.name, self.experiment_id, self.answer, self.calls = name, experiment_id, answer, 0

    def __call__(self, proposals):
        self.calls += 1
        if self.answer == "approve":
            return make_approval(proposals, self.experiment_id or proposals[0]["experiment_id"], self.name)
        return self.answer


def run(t, gate=None, **kw) -> TeamSession:
    return run_session(t.monitor, t.planner, gate if gate is not None else Gate(), t.executor, t.analyst,
                       sessions_dir=t.sessions_dir, **kw)


def faults(t) -> list[str]:
    return [c for c in t.docker.calls if c in FAULT_CALLS]


# ---------------------------------------------------------------------------------------------- happy path
def test_full_session_runs_the_stages_in_order_and_is_written(tmp_path):
    t = make_team(tmp_path)
    seen = []
    s = run(t, experiment_id="telemetry_stall", on_step=lambda kind, payload: seen.append(kind))
    assert s.outcome == "completed" and s.run_id
    assert [x.agent for x in s.steps] == ["monitor", "planner", "executor", "analyst"]
    assert seen == ["monitor", "planner", "gate", "executor", "analyst"]
    planner, executor = s.steps[1], s.steps[2]
    assert planner.ended_utc <= s.approval.approved_at_utc <= executor.started_utc    # the gate sits between them
    assert s.approval.approved_by == "Anshu" and s.approval.experiment_id == "telemetry_stall"
    assert s.approval.shown.predicted_symptoms == list(SYMPTOMS) and s.approval.shown.risks == list(RISKS)
    assert t.runner.runs == 1 and "pause" in faults(t) and "unpause" in faults(t)
    assert s.run_id in executor.evidence_refs
    record = json.loads((t.cfg.data_dir / "runs" / f"{s.run_id}.json").read_text(encoding="utf-8"))
    assert record["request"]["approved_by"] == "Anshu" and record["state"] == "COMPLETED"
    path = t.sessions_dir / f"{s.session_id}.json"
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert TeamSession.model_validate(on_disk) == s
    assert schema_errors(on_disk) == []
    assert not list(t.sessions_dir.glob("*.tmp"))                                     # atomic write leaves no temp file


def test_monitor_and_executor_never_use_the_llm_even_when_ai_is_on(tmp_path):
    t = make_team(tmp_path, provider=_provider(content="not json"))
    s = run(t)
    by = {x.agent: x for x in s.steps}
    assert by["monitor"].uses_llm is False and by["executor"].uses_llm is False
    assert by["planner"].uses_llm is True and by["analyst"].uses_llm is True


# ---------------------------------------------------------------------------------------------- monitor
@pytest.mark.parametrize("knob", ["api_down", "stale", "no_baseline"])
def test_unhealthy_monitor_refuses_and_nothing_is_planned_or_executed(tmp_path, knob):
    t = make_team(tmp_path, baseline=knob != "no_baseline")
    if knob == "api_down":
        t.world.api_down = True
    if knob == "stale":                     # forwarder frozen out of band: HTTP 200, createdDateTime 10 s old
        t.world.mutate("fms-forwarder", paused=True, status="paused")
        t.world.last_created -= timedelta(seconds=10)
    gate = Gate()
    s = run(t, gate=gate)
    assert s.outcome == "refused" and [x.agent for x in s.steps] == ["monitor"]
    assert s.steps[0].status == "refused" and s.approval is None and s.run_id is None
    assert gate.calls == 0 and t.runner.runs == 0 and t.docker.calls == []
    assert (t.sessions_dir / f"{s.session_id}.json").is_file()


def test_monitor_exception_becomes_an_error_step(tmp_path):
    t = make_team(tmp_path)
    t.monitor.observer = SimpleNamespace(observe=lambda timeout_s=None: (_ for _ in ()).throw(RuntimeError("boom")))
    s = run(t)
    assert s.outcome == "error" and [x.agent for x in s.steps] == ["monitor"]
    assert s.steps[0].status == "error" and "boom" in s.steps[0].decision and t.docker.calls == []


# ---------------------------------------------------------------------------------------------- planner + gate
def test_unknown_experiment_is_rejected_before_the_gate(tmp_path):
    t = make_team(tmp_path)
    gate = Gate()
    s = run(t, gate=gate, experiment_id="rm_rf_everything")
    assert s.outcome == "refused" and [x.agent for x in s.steps] == ["monitor", "planner"]
    assert s.steps[1].status == "refused" and "rm_rf_everything" in s.steps[1].decision
    assert gate.calls == 0 and t.runner.runs == 0 and t.docker.calls == []


@pytest.mark.parametrize("answer", [None, False, True, "APPROVE", {"approved_by": "Anshu"}])
def test_no_approval_record_means_nothing_executes(tmp_path, answer):
    t = make_team(tmp_path)
    s = run(t, gate=Gate(answer=answer))
    assert s.outcome == "refused" and s.approval is None and s.run_id is None
    assert [x.agent for x in s.steps] == ["monitor", "planner"]
    assert t.runner.runs == 0 and t.docker.calls == []


def test_approval_for_a_different_experiment_than_requested_is_refused(tmp_path):
    t = make_team(tmp_path)
    forged = ApprovalRecord(approved_by="Anshu", approved_at_utc="2026-11-02T15:00:00.000+00:00",
                            experiment_id="service_crash", shown={"rank": 1, "reasons": [], "predicted_symptoms": [], "risks": []})
    s = run(t, gate=Gate(answer=forged), experiment_id="telemetry_stall")
    assert s.outcome == "refused" and t.runner.runs == 0 and t.docker.calls == []


def test_make_approval_refuses_blank_names_and_unlisted_experiments(tmp_path):
    proposals = make_team(tmp_path).planner.run(None)[1]
    with pytest.raises(ValueError):
        make_approval(proposals, "telemetry_stall", "   ")
    with pytest.raises(ValueError):
        make_approval(proposals, "service_crash", "Anshu")


def test_gate_exception_ends_the_session_without_execution(tmp_path):
    t = make_team(tmp_path)

    def gate(_):
        raise RuntimeError("gate crashed")
    s = run(t, gate=gate)
    assert s.outcome == "error" and t.runner.runs == 0 and t.docker.calls == []


@pytest.mark.parametrize("provider, reason", [(None, "AI disabled"),
                                              (_provider(exc=httpx.ReadTimeout("timed out")), "unreachable"),
                                              (_provider(content="{not json"), "non-JSON"),
                                              (_provider({"summary": "x", "order": [{"id": "made_up@host", "rationale": "r"}]}),
                                               "permutation")])
def test_ai_off_timeout_or_invalid_answer_falls_back_and_the_session_completes(tmp_path, provider, reason):
    t = make_team(tmp_path, provider=provider)
    s = run(t)
    planner = s.steps[1]
    assert planner.status == "fallback" and reason in planner.fallback_reason
    assert s.outcome == "completed" and s.steps[-1].agent == "analyst"


def test_valid_ai_reordering_is_used(tmp_path):
    answer = {"summary": "stall first", "order": [{"id": "telemetry_stall@fms-forwarder", "rationale": "most informative"}]}
    t = make_team(tmp_path, provider=_provider(answer))
    step, proposals = t.planner.run(None)
    assert step.status == "ok" and step.fallback_reason is None and step.uses_llm
    assert proposals[0]["experiment_id"] == "telemetry_stall" and "most informative" in proposals[0]["reasons"][0]


def test_planner_exception_becomes_an_error_step(tmp_path):
    t = make_team(tmp_path, runs_loader=lambda: (_ for _ in ()).throw(OSError("disk gone")))
    s = run(t)
    assert s.outcome == "error" and s.steps[-1].agent == "planner" and s.steps[-1].status == "error"
    assert "disk gone" in s.steps[-1].decision and t.docker.calls == []


# ---------------------------------------------------------------------------------------------- executor
def test_busy_controller_is_recorded_as_refused_with_its_own_reason(tmp_path):
    t = make_team(tmp_path)
    t.ctl.begin("20261102T000000Z-other1")
    try:
        s = run(t)
    finally:
        t.ctl.end("20261102T000000Z-other1")
    ex = s.steps[-1]
    assert s.outcome == "refused" and ex.agent == "executor" and ex.status == "refused"
    assert "already active" in ex.decision and s.run_id is None and faults(t) == []


def test_latched_controller_is_recorded_as_refused_with_its_own_reason(tmp_path):
    t = make_team(tmp_path)
    t.ctl.latch("rollback not verified in an earlier run")
    s = run(t)
    ex = s.steps[-1]
    assert s.outcome == "refused" and ex.status == "refused" and "rollback not verified" in ex.decision
    assert faults(t) == [] and t.runner.runs == 1                  # asked once, refused by the controller, not retried


def test_executor_exception_is_an_error_and_is_never_retried(tmp_path):
    t = make_team(tmp_path, runner_fail=RuntimeError("runner exploded"))
    s = run(t)
    assert s.outcome == "error" and s.steps[-1].agent == "executor" and s.steps[-1].status == "error"
    assert t.runner.runs == 1 and "runner exploded" in s.steps[-1].decision


@pytest.mark.parametrize("approval", [None, {"approved_by": "Anshu", "experiment_id": "telemetry_stall"}, "Anshu"])
def test_executor_refuses_to_run_without_an_approval_record(tmp_path, approval):
    t = make_team(tmp_path)
    proposals = t.planner.run(None)[1]
    with pytest.raises(TypeError):
        t.executor.run(approval, proposals[0], "20261102T150000Z-abc123")
    assert t.runner.runs == 0 and t.docker.calls == []


def test_executor_builds_the_request_like_the_cli_run(tmp_path):
    t = make_team(tmp_path)
    proposals = t.planner.run(None)[1]
    seen = []
    t.runner.inner = SimpleNamespace(run=lambda req: seen.append(req) or {"run_id": "r", "state": "COMPLETED",
                                                                         "stop_reason": "duration_elapsed"})
    t.executor.run(make_approval(proposals, "telemetry_stall", "Anshu"), proposals[0], "20261102T150000Z-abc123")
    (req,) = seen
    assert set(req) == {"experiment_type", "target", "duration_s", "approved_by", "hypothesis"}
    assert req["experiment_type"] == "telemetry_stall" and req["target"] == "fms-forwarder"
    assert req["approved_by"] == "Anshu" and req["duration_s"] == 2 and "20261102T150000Z-abc123" in req["hypothesis"]


# ---------------------------------------------------------------------------------------------- analyst
def test_analyst_lists_ai_answers_that_fail_the_grounding_check(tmp_path):
    bad = "The fms-server is not recovering properly, possibly due to a delay in DNS resolution or HTTP client caching."
    provider = _provider({"analyses": [_item(STALL_SILENT, ["20261010T180000Z-a"], root_cause=bad)]})
    step = AnalystAgent(lambda: RUNS, provider=provider).run(RUNS[0])
    assert step.status == "fallback" and step.uses_llm
    assert f"rejected {STALL_SILENT}" in step.output_summary and "rules out" in step.output_summary
    assert "20261010T180000Z-a" in step.evidence_refs


def test_analyst_without_ai_gives_score_and_rule_based_findings(tmp_path):
    step = AnalystAgent(lambda: RUNS).run(RUNS[0])
    assert step.status == "fallback" and step.fallback_reason == "AI disabled" and not step.uses_llm
    assert "score" in step.output_summary and f"{len(FINDINGS)} finding" in step.output_summary
