"""Monitor, Planner and Analyst agents. Each wraps existing, tested code and returns an AgentStep for the trace.

None of them can touch Docker, the shell, the safety controller, the orchestrator or fault adapters: those live only
behind the Safety Executor (executor_agent.py). Enforced by tests/test_team_import_guard.py.
"""
from __future__ import annotations

import time
from typing import Callable

from ..ai import ai_analyse, ai_plan
from ..findings import derive_findings
from ..planner import plan
from ..scoring import score_run
from ..telemetry import Freshness, FreshnessTracker
from .trace import AgentStep, utc_now

RunsLoader = Callable[[], list[dict]]


def _step(agent: str, role: str, started: str, **fields) -> AgentStep:
    fields.setdefault("evidence_refs", [])
    fields.setdefault("fallback_reason", None)
    return AgentStep(agent=agent, role=role, started_utc=started, ended_utc=utc_now(), **fields)


class MonitorAgent:
    """Deterministic. Polls the rFMS observer N times through the telemetry verifier and checks a baseline exists."""

    role = "observe: rFMS freshness via the telemetry verifier + stored baseline (deterministic)"

    def __init__(self, observer, stale_threshold_s: float, latest_baseline: Callable[[], tuple[str, dict] | None],
                 samples: int = 6, interval_s: float = 0.5, sleep: Callable[[float], None] = time.sleep) -> None:
        self.observer, self.stale_threshold_s, self.latest_baseline = observer, stale_threshold_s, latest_baseline
        self.samples, self.interval_s, self.sleep = samples, interval_s, sleep

    def run(self) -> tuple[AgentStep, bool]:
        started = utc_now()
        tracker = FreshnessTracker(self.stale_threshold_s)
        seen = []
        for i in range(self.samples):
            obs = self.observer.observe()
            seen.append((obs, tracker.update(obs)))
            if i < self.samples - 1:
                self.sleep(self.interval_s)
        fresh = sum(a.freshness == Freshness.FRESH for _, a in seen)
        http_ok = sum(o.http_ok for o, _ in seen)
        advanced = any(a.advanced for _, a in seen)
        ages = [a.data_age_s for _, a in seen if a.data_age_s is not None]
        baseline = self.latest_baseline()
        problems = []
        if fresh < self.samples:
            problems.append(f"only {fresh}/{self.samples} polls FRESH "
                            f"({', '.join(sorted({a.freshness.value for _, a in seen if a.freshness != Freshness.FRESH}))})")
        if self.samples > 1 and not advanced:
            problems.append("createdDateTime did not advance")
        if baseline is None:
            problems.append("no stored baseline (run `mcop baseline`)")
        healthy = not problems
        summary = (f"{fresh}/{self.samples} FRESH, HTTP 200 {http_ok}/{self.samples}, createdDateTime advanced: "
                   f"{advanced}, max data age {max(ages) if ages else 'n/a'} s; baseline: "
                   f"{baseline[0] if baseline else 'missing'}")
        return _step("monitor", self.role, started, uses_llm=False,
                     inputs_summary=f"{self.samples} polls every {self.interval_s} s, stale threshold "
                                    f"{self.stale_threshold_s} s",
                     output_summary=summary,
                     decision="healthy: hand over to the Planner" if healthy
                     else "unhealthy: session refused, nothing planned or executed (" + "; ".join(problems) + ")",
                     evidence_refs=[baseline[0]] if baseline else [],
                     status="ok" if healthy else "refused"), healthy


class PlannerAgent:
    """Rule-based ranking always runs (planner.plan). The local LLM may only reorder it (ai.ai_plan, which accepts an
    exact permutation of the allowlisted candidates and otherwise falls back to the rule order)."""

    role = "propose: rank allowlisted experiments (rule-based; optional advisory LLM reorder)"

    def __init__(self, catalog: dict, dep_map: dict, runs_loader: RunsLoader, max_duration_s: int, provider=None) -> None:
        self.catalog, self.dep_map, self.runs_loader = catalog, dep_map, runs_loader
        self.max_duration_s, self.provider = max_duration_s, provider

    def run(self, experiment_id: str | None) -> tuple[AgentStep, list[dict]]:
        started = utc_now()
        runs = self.runs_loader()
        entries = plan(self.catalog, self.dep_map, runs, self.max_duration_s)
        by_id = {f"{e['experiment_type']}@{e['target']}": e for e in entries}
        if self.provider is not None:
            result = ai_plan(entries, derive_findings(runs), self.provider)
        else:
            result = ai_plan(entries, [], None)
        ai_used = result["provider"] != "rule-based"
        proposals = []
        for rank, o in enumerate(result["order"], 1):
            e = by_id[o["id"]]
            spec = self.catalog[e["experiment_type"]]
            reasons = ([f"AI: {o['rationale']}"] if ai_used and o.get("rationale") else []) + list(e["rationale"])
            proposals.append({"rank": rank, "experiment_id": e["experiment_type"], "target": e["target"],
                              "mechanism": e["mechanism"], "reasons": reasons,
                              "predicted_symptoms": list(spec.get("expected_symptoms", [])),
                              "risks": list(spec.get("risks", [])), "suggested_duration_s": e["suggested_duration_s"],
                              "rule_based_rank": e["rank"]})
        ranking = ", ".join(f"{p['rank']}. {p['experiment_id']}@{p['target']}" for p in proposals)
        fields = dict(uses_llm=self.provider is not None,
                      inputs_summary=f"{len(self.catalog)} allowlisted experiment types, {len(runs)} stored run records, "
                                     f"AI {'on (' + self.provider.name + ')' if self.provider is not None else 'off'}",
                      output_summary=f"ranking: {ranking}" + (f"; AI summary: {result['summary']}" if ai_used else ""),
                      evidence_refs=["config/experiments.json", "config/dependency_map.json"])
        allowed = {p["experiment_id"] for p in proposals}
        if experiment_id is not None and experiment_id not in allowed:
            return _step("planner", self.role, started, decision=f"requested experiment_id {experiment_id!r} is not "
                         f"in the allowlisted catalogue {sorted(allowed)}; refused before the human gate",
                         status="refused", **fields), proposals
        chosen = experiment_id or proposals[0]["experiment_id"]
        return _step("planner", self.role, started,
                     decision=f"proposals ready for the human gate ({'requested' if experiment_id else 'top'}: {chosen})",
                     status="ok" if ai_used else "fallback",
                     fallback_reason=None if ai_used else result.get("fallback_reason", "AI disabled"),
                     **fields), proposals


class AnalystAgent:
    """Scores the run (scoring.score_run), derives findings over the stored runs including this one
    (findings.derive_findings), then explains them: AI analyst with the grounding check, or rule-based text."""

    role = "explain: score + findings for the run (rule-based; optional advisory LLM with grounding check)"

    def __init__(self, runs_loader: RunsLoader, provider=None) -> None:
        self.runs_loader, self.provider = runs_loader, provider

    def run(self, record: dict) -> AgentStep:
        started = utc_now()
        run_id = record["run_id"]
        score = score_run(record)
        runs = self.runs_loader()
        if run_id not in {r["run_id"] for r in runs}:
            runs = runs + [record]
        findings = derive_findings(runs)
        analysis = ai_analyse(findings, self.provider)
        mine = [a for a in analysis["analyses"] if run_id in a["evidence_runs"]]
        rejected = analysis.get("rejected", [])
        score_txt = (f"score {score['score']}{' (partial window)' if score['partial'] else ''}" if score["scorable"]
                     else f"score not computed ({score.get('reason', 'not scorable')})")
        parts = [f"run {run_id} {record['state']} ({record.get('stop_reason')}); {score_txt}",
                 f"{len(findings)} finding(s) over {len(runs)} run(s), {len(mine)} cite this run"]
        parts += [f"rejected {r['finding']}: {r['reason']}" for r in rejected]
        if analysis["provider"] == "rule-based":
            status = "fallback"
            reason = analysis.get("fallback_reason") or "no findings to analyse; nothing sent to the AI"
        elif analysis.get("ai_items_rejected_or_missing"):
            status = "fallback"
            reason = (f"{analysis['ai_items_rejected_or_missing']} AI answer(s) rejected or missing; rule-based text "
                      "used for them")
        else:
            status, reason = "ok", None
        decision = ("; ".join(f"{a['finding']} {a['rule'] if 'rule' in a else ''}: {a['root_cause'][:140]} "
                              f"[{a['source']}]" for a in mine) or "no finding cites this run")
        return _step("analyst", self.role, started, uses_llm=self.provider is not None,
                     inputs_summary=f"run record {run_id}, {len(runs)} run records, "
                                    f"AI {'on (' + self.provider.name + ')' if self.provider is not None else 'off'}",
                     output_summary="; ".join(parts), decision=decision,
                     evidence_refs=[run_id] + [a["finding"] for a in mine], status=status, fallback_reason=reason)
