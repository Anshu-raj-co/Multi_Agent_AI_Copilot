"""Session trace written by the agent-team pipeline: one AgentStep per hand-off, plus the human approval.
Strict: unknown fields are rejected. Contract: contracts/team_session.schema.json."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

UTC_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\+00:00$"
SESSION_ID_PATTERN = r"^\d{8}T\d{6}Z-[0-9a-f]{6}$"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def new_session_id() -> str:
    """Same style as run ids (orchestrator._new_run_id): UTC timestamp + 6 hex."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AgentStep(_Strict):
    agent: Literal["monitor", "planner", "executor", "analyst"]
    role: str
    uses_llm: bool
    started_utc: str = Field(pattern=UTC_PATTERN)
    ended_utc: str = Field(pattern=UTC_PATTERN)
    inputs_summary: str
    output_summary: str
    decision: str
    evidence_refs: list[str]
    status: Literal["ok", "fallback", "refused", "error"]
    fallback_reason: str | None


class Shown(_Strict):
    """What the approver saw for the chosen experiment."""
    rank: int
    reasons: list[str]
    predicted_symptoms: list[str]
    risks: list[str]


class ApprovalRecord(_Strict):
    approved_by: str = Field(min_length=1)
    approved_at_utc: str = Field(pattern=UTC_PATTERN)
    experiment_id: str
    shown: Shown

    @field_validator("approved_by")
    @classmethod
    def _named(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("approved_by must name a person")
        return v.strip()


class TeamSession(_Strict):
    session_id: str = Field(pattern=SESSION_ID_PATTERN)
    started_utc: str = Field(pattern=UTC_PATTERN)
    steps: list[AgentStep]
    approval: ApprovalRecord | None
    run_id: str | None
    outcome: Literal["completed", "aborted", "refused", "error"]
