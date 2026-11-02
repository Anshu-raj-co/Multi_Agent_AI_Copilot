"""Safety Executor: the only agent-team module that reaches the safety controller and the orchestrator.

It never uses an LLM and cannot import the AI client (tests/test_team_import_guard.py). It calls the controller exactly
as the CLI `run` command does: build the request, `SafetyController.validate`, then `ExperimentRunner.run`. All safety
behaviour (allowlist, single-run lock, watchdog, guardrails, rollback, recovery check, latch) stays in that code.
"""
from __future__ import annotations

from ..config import ExperimentSpec
from ..orchestrator import ExperimentRunner
from ..safety import Busy, Latched, RequestRejected, SafetyController, SafetyError
from .trace import AgentStep, ApprovalRecord, utc_now

ROLE = "execute: one approved, allowlisted experiment through the safety controller (deterministic, never an LLM)"


class SafetyExecutorAgent:
    def __init__(self, catalog: dict[str, ExperimentSpec], controller: SafetyController, runner: ExperimentRunner) -> None:
        self.catalog, self.ctl, self.runner = catalog, controller, runner

    def request(self, approval: ApprovalRecord, proposal: dict, session_id: str) -> dict:
        """Same fields as `mcop run`: the target comes from the catalogue, the duration from the plan (capped again by
        the controller's own validation)."""
        spec = self.catalog[approval.experiment_id]
        if proposal["experiment_id"] != approval.experiment_id or proposal["target"] not in spec.allowed_targets:
            raise RequestRejected("proposal does not match the approved, allowlisted experiment")
        predicted = "; ".join(approval.shown.predicted_symptoms)
        return {"experiment_type": approval.experiment_id, "target": proposal["target"],
                "duration_s": int(proposal["suggested_duration_s"]), "approved_by": approval.approved_by,
                "hypothesis": f"Team session {session_id} (planner rank {approval.shown.rank}). Predicted: {predicted}"[:500]}

    def run(self, approval: ApprovalRecord, proposal: dict, session_id: str) -> tuple[AgentStep, dict | None]:
        if not isinstance(approval, ApprovalRecord):
            raise TypeError("the Safety Executor runs nothing without an ApprovalRecord from the human gate")
        started = utc_now()
        common = dict(agent="executor", role=ROLE, uses_llm=False, started_utc=started)
        try:
            req = self.request(approval, proposal, session_id)
            self.ctl.validate(req)
            record = self.runner.run(req)          # one call; never retried
        except (Busy, Latched, RequestRejected, SafetyError) as exc:
            kind = {Busy: "BUSY", Latched: "LATCHED_UNSAFE / stop engaged", RequestRejected: "request rejected"}.get(
                type(exc), type(exc).__name__)
            return AgentStep(**common, ended_utc=utc_now(),
                             inputs_summary=f"approved by {approval.approved_by}: {approval.experiment_id}",
                             output_summary=f"controller refused ({kind})", decision=f"refused by the safety "
                             f"controller: {exc}", evidence_refs=[], status="refused", fallback_reason=None), None
        rb, rc, imp = record.get("rollback", {}), record.get("recovery", {}), record.get("impact", {})
        return AgentStep(
            **common, ended_utc=utc_now(),
            inputs_summary=(f"approved by {approval.approved_by}: {req['experiment_type']} on {req['target']} for "
                            f"{req['duration_s']} s"),
            output_summary=(f"run {record['run_id']} {record['state']} (stop_reason={record.get('stop_reason')}); "
                            f"fault verified {imp.get('fault_verified')}, stale detected {imp.get('stale_detected')} "
                            f"(ttd {imp.get('time_to_detection_s')} s), HTTP-200 ratio during fault "
                            f"{imp.get('http_ok_ratio_during_fault')}; rollback verified {rb.get('verified')} by "
                            f"{rb.get('by')}; recovery verified {rc.get('verified')} after {rc.get('time_to_verified_s')} s"),
            decision=("run completed; hand over to the Analyst" if record["state"] == "COMPLETED"
                      else f"run ended {record['state']}; hand over to the Analyst"),
            evidence_refs=[record["run_id"], f"runs/{record['run_id']}.json (evidence store)"],
            status="ok", fallback_reason=None), record
