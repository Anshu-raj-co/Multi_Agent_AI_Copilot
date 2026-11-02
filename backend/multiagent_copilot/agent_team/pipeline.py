"""Explicit pipeline: Monitor -> Planner -> HUMAN GATE -> Safety Executor -> Analyst. Every hand-off is recorded.

Rules: the gate must return an ApprovalRecord for an allowlisted proposal or nothing executes; a stage exception becomes
a step with status "error" and ends the session; an experiment is never retried; controller refusals (BUSY,
LATCHED_UNSAFE) are recorded as "refused" with the controller's own reason. The session is written atomically to
<sessions_dir>/<session_id>.json. This module imports only the agents and the trace (tests/test_team_import_guard.py).
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Callable

from .agents import AnalystAgent, MonitorAgent, PlannerAgent
from .executor_agent import SafetyExecutorAgent
from .trace import SESSION_ID_PATTERN, AgentStep, ApprovalRecord, Shown, TeamSession, new_session_id, utc_now

Gate = Callable[[list[dict]], "ApprovalRecord | None"]
OnStep = Callable[[str, object], None]   # (kind, AgentStep | ApprovalRecord | None); kind includes "gate"


def make_approval(proposals: list[dict], experiment_id: str, approved_by: str) -> ApprovalRecord:
    """The record a named human gives at the gate, holding what they were shown. Raises ValueError if the experiment
    is not one of the proposals or the name is blank."""
    p = next((p for p in proposals if p["experiment_id"] == experiment_id), None)
    if p is None:
        raise ValueError(f"{experiment_id!r} is not one of the proposed experiments {[x['experiment_id'] for x in proposals]}")
    return ApprovalRecord(approved_by=approved_by, approved_at_utc=utc_now(), experiment_id=experiment_id,
                          shown=Shown(rank=p["rank"], reasons=list(p["reasons"]),
                                      predicted_symptoms=list(p["predicted_symptoms"]), risks=list(p["risks"])))


def _error_step(agent: str, started: str, exc: BaseException, uses_llm: bool) -> AgentStep:
    return AgentStep(agent=agent, role="stage raised an exception", uses_llm=uses_llm, started_utc=started,
                     ended_utc=utc_now(), inputs_summary="", output_summary="",
                     decision=f"{type(exc).__name__}: {exc}"[:500], evidence_refs=[], status="error",
                     fallback_reason=None)


def write_session(sessions_dir: Path, session: TeamSession) -> Path:
    sessions_dir.mkdir(parents=True, exist_ok=True)
    path = sessions_dir / f"{session.session_id}.json"
    tmp = sessions_dir / f".{session.session_id}.json.tmp"
    tmp.write_text(session.model_dump_json(indent=2) + "\n", encoding="utf-8")
    for attempt in range(5):        # Windows: a concurrent reader can briefly block the replace
        try:
            os.replace(tmp, path)
            return path
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.05)
    return path


def run_session(monitor: MonitorAgent, planner: PlannerAgent, gate: Gate, executor: SafetyExecutorAgent,
                analyst: AnalystAgent, *, sessions_dir: Path, experiment_id: str | None = None,
                on_step: OnStep | None = None) -> TeamSession:
    session_id, started = new_session_id(), utc_now()
    steps: list[AgentStep] = []
    state: dict = {"approval": None, "run_id": None}
    notify = on_step or (lambda kind, payload: None)

    def finish(outcome: str) -> TeamSession:
        s = TeamSession(session_id=session_id, started_utc=started, steps=steps, approval=state["approval"],
                        run_id=state["run_id"], outcome=outcome)
        write_session(sessions_dir, s)
        return s

    def stage(agent: str, obj, fn):
        t0 = utc_now()
        try:
            return True, fn()
        except Exception as exc:  # noqa: BLE001 - any stage failure is recorded and ends the session
            steps.append(_error_step(agent, t0, exc, getattr(obj, "provider", None) is not None))
            notify(agent, steps[-1])
            return False, None

    # 1. Monitor: unhealthy -> refused, nothing planned or executed
    ok, res = stage("monitor", monitor, monitor.run)
    if not ok:
        return finish("error")
    step, healthy = res
    steps.append(step)
    notify("monitor", step)
    if not healthy:
        return finish("refused")

    # 2. Planner: unknown experiment_id is refused here, before the gate
    ok, res = stage("planner", planner, lambda: planner.run(experiment_id))
    if not ok:
        return finish("error")
    step, proposals = res
    steps.append(step)
    notify("planner", step)
    if step.status == "refused":
        return finish("refused")

    # 3. HUMAN GATE: only an ApprovalRecord for an allowlisted proposal (and the requested one, if any) passes
    try:
        approval = gate(proposals)
    except Exception:  # noqa: BLE001 - the gate failing never defaults to approval
        notify("gate", None)
        return finish("error")
    allowed = {p["experiment_id"] for p in proposals}
    if (not isinstance(approval, ApprovalRecord) or approval.experiment_id not in allowed
            or (experiment_id is not None and approval.experiment_id != experiment_id)):
        notify("gate", None)
        return finish("refused")
    state["approval"] = approval
    notify("gate", approval)

    # 4. Safety Executor: one call, never retried
    proposal = next(p for p in proposals if p["experiment_id"] == approval.experiment_id)
    ok, res = stage("executor", executor, lambda: executor.run(approval, proposal, session_id))
    if not ok:
        return finish("error")
    step, record = res
    steps.append(step)
    notify("executor", step)
    if record is None:
        return finish("refused")
    state["run_id"] = record["run_id"]

    # 5. Analyst
    ok, res = stage("analyst", analyst, lambda: analyst.run(record))
    if not ok:
        return finish("error")
    steps.append(res)
    notify("analyst", res)
    return finish("completed" if record["state"] == "COMPLETED" else "aborted")


# ------------------------------------------------------------------------------------------- reading sessions
def session_files(*dirs: Path) -> list[Path]:
    """Session files from the given directories, newest first (ids start with a UTC timestamp)."""
    files = {p.name: p for d in reversed(dirs) if d.is_dir() for p in d.glob("*.json")
             if re.match(SESSION_ID_PATTERN, p.stem)}
    return [files[k] for k in sorted(files, reverse=True)]


def load_session(path: Path) -> TeamSession:
    return TeamSession.model_validate(json.loads(path.read_text(encoding="utf-8")))


def find_session(session_id: str, *dirs: Path) -> Path | None:
    if not re.match(SESSION_ID_PATTERN, session_id):
        raise ValueError(f"not a session id: {session_id!r}")
    return next((d / f"{session_id}.json" for d in dirs if (d / f"{session_id}.json").is_file()), None)


LABEL = {"monitor": "Monitor", "planner": "Planner", "executor": "Executor", "analyst": "Analyst"}


def _secs(a: str, b: str) -> str:
    from datetime import datetime
    return f"{(datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds():.1f} s"


def render_session(s: TeamSession) -> str:
    lines = [f"Team session {s.session_id}  outcome={s.outcome}  run_id={s.run_id or 'none'}  started {s.started_utc}"]

    def add(step: AgentStep) -> None:
        badge = "LLM" if step.uses_llm else "deterministic"
        lines.append(f"[{LABEL[step.agent]}] {step.status.upper()} ({badge}, {_secs(step.started_utc, step.ended_utc)})"
                     f"  {step.role}")
        lines.append(f"    in:       {step.inputs_summary}")
        lines.append(f"    out:      {step.output_summary}")
        lines.append(f"    decision: {step.decision}")
        if step.fallback_reason:
            lines.append(f"    fallback: {step.fallback_reason}")
        if step.evidence_refs:
            lines.append(f"    evidence: {', '.join(step.evidence_refs)}")

    a = s.approval
    human = (f"[HUMAN] approved by {a.approved_by} at {a.approved_at_utc}: {a.experiment_id} (planner rank "
             f"{a.shown.rank})" if a else "[HUMAN] not approved: nothing executed")
    for step in s.steps:
        if step.agent == "executor":
            lines.append(human)
        add(step)
    reached_gate = any(x.agent == "planner" and x.status in ("ok", "fallback") for x in s.steps)
    if reached_gate and not any(x.agent == "executor" for x in s.steps):
        lines.append(human)
    return "\n".join(lines)
