"""Strict trace models for the agent team (agent_team/trace.py) and their JSON Schema contract."""
from __future__ import annotations

import json
import re

import pytest
from pydantic import ValidationError

from multiagent_copilot.agent_team.trace import AgentStep, ApprovalRecord, Shown, TeamSession, new_session_id, utc_now
from multiagent_copilot.config import REPO_ROOT

SCHEMA = json.loads((REPO_ROOT / "contracts" / "team_session.schema.json").read_text(encoding="utf-8"))


def step(**kw) -> dict:
    base = {"agent": "monitor", "role": "observe", "uses_llm": False, "started_utc": utc_now(), "ended_utc": utc_now(),
            "inputs_summary": "3 polls", "output_summary": "FRESH", "decision": "healthy", "evidence_refs": [],
            "status": "ok", "fallback_reason": None}
    return {**base, **kw}


def approval(**kw) -> dict:
    base = {"approved_by": "Anshu", "approved_at_utc": utc_now(), "experiment_id": "telemetry_stall",
            "shown": {"rank": 1, "reasons": ["never run"], "predicted_symptoms": ["HTTP 200"], "risks": ["none"]}}
    return {**base, **kw}


def session(**kw) -> dict:
    base = {"session_id": new_session_id(), "started_utc": utc_now(), "steps": [step()], "approval": approval(),
            "run_id": "20261102T150000Z-abc123", "outcome": "completed"}
    return {**base, **kw}


# ---------------------------------------------------------------------------------------------------- models
def test_valid_session_round_trips():
    s = TeamSession.model_validate(session())
    assert TeamSession.model_validate_json(s.model_dump_json()) == s


@pytest.mark.parametrize("model, doc", [(AgentStep, step(extra="x")), (ApprovalRecord, approval(extra="x")),
                                        (TeamSession, session(extra="x")),
                                        (Shown, {"rank": 1, "reasons": [], "predicted_symptoms": [], "risks": [], "x": 1})])
def test_unknown_fields_are_rejected(model, doc):
    with pytest.raises(ValidationError):
        model.model_validate(doc)


@pytest.mark.parametrize("name", ["", "   ", "\t\n"])
def test_blank_approver_is_rejected(name):
    with pytest.raises(ValidationError):
        ApprovalRecord.model_validate(approval(approved_by=name))


@pytest.mark.parametrize("field, value", [("status", "maybe"), ("status", "OK"), ("agent", "gate"), ("agent", "llm"),
                                          ("uses_llm", "yes"), ("evidence_refs", "run-1")])
def test_bad_step_values_are_rejected(field, value):
    with pytest.raises(ValidationError):
        AgentStep.model_validate(step(**{field: value}))


@pytest.mark.parametrize("field, value", [("outcome", "success"), ("session_id", "abc"),
                                          ("session_id", "20261102T150000Z-ABCDEF"), ("session_id", "../../etc/passwd")])
def test_bad_session_values_are_rejected(field, value):
    with pytest.raises(ValidationError):
        TeamSession.model_validate(session(**{field: value}))


def test_session_id_uses_the_run_id_style():
    ids = {new_session_id() for _ in range(50)}
    assert len(ids) == 50 and all(re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{6}", i) for i in ids)


# ---------------------------------------------------------------------------------------------------- schema
def _resolve(schema: dict, root: dict) -> dict:
    while "$ref" in schema:
        schema = root["$defs"][schema["$ref"].split("/")[-1]]
    return schema


def schema_errors(doc, schema: dict = SCHEMA, root: dict | None = None, path: str = "$") -> list[str]:
    """Validator for the JSON-Schema subset the contracts use (type, enum, pattern, minLength, required,
    properties, additionalProperties: false, items, $ref, anyOf). No third-party dependency."""
    root = root or schema
    s = _resolve(schema, root)
    if "anyOf" in s:
        branches = [schema_errors(doc, b, root, path) for b in s["anyOf"]]
        if all(branches):
            return [f"{path}: matches no anyOf branch: {min(branches, key=len)}"]
    types = s.get("type")
    py = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}
    if types:
        ok = False
        for t in ([types] if isinstance(types, str) else types):
            if t == "integer":
                ok |= isinstance(doc, int) and not isinstance(doc, bool)
            else:
                ok |= isinstance(doc, py[t])
        if not ok:
            return [f"{path}: expected {types}, got {type(doc).__name__}"]
    errs = []
    if "enum" in s and doc not in s["enum"]:
        errs.append(f"{path}: {doc!r} not in {s['enum']}")
    if isinstance(doc, str):
        if "pattern" in s and not re.search(s["pattern"], doc):
            errs.append(f"{path}: {doc!r} does not match {s['pattern']}")
        if len(doc) < s.get("minLength", 0):
            errs.append(f"{path}: shorter than {s['minLength']}")
    if isinstance(doc, dict):
        errs += [f"{path}: missing {k}" for k in s.get("required", []) if k not in doc]
        props = s.get("properties", {})
        if s.get("additionalProperties") is False:
            errs += [f"{path}: unexpected {k}" for k in doc if k not in props]
        for k, v in doc.items():
            if k in props:
                errs += schema_errors(v, props[k], root, f"{path}.{k}")
    if isinstance(doc, list) and "items" in s:
        for i, v in enumerate(doc):
            errs += schema_errors(v, s["items"], root, f"{path}[{i}]")
    return errs


def test_schema_is_in_the_contracts_style():
    assert SCHEMA["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert SCHEMA["$id"] == "multiagent-copilot/team_session.schema.json"
    assert SCHEMA["additionalProperties"] is False


@pytest.mark.parametrize("name, model", [("TeamSession", TeamSession), ("AgentStep", AgentStep),
                                         ("ApprovalRecord", ApprovalRecord), ("Shown", Shown)])
def test_schema_fields_match_the_models(name, model):
    s = SCHEMA if name == "TeamSession" else SCHEMA["$defs"][name]
    assert set(s["properties"]) == set(model.model_fields), name
    assert set(s["required"]) == set(model.model_fields), name
    assert s["additionalProperties"] is False


def test_model_output_validates_against_the_schema():
    doc = json.loads(TeamSession.model_validate(session()).model_dump_json())
    assert schema_errors(doc) == []
    refused = json.loads(TeamSession.model_validate(session(approval=None, run_id=None, outcome="refused")).model_dump_json())
    assert schema_errors(refused) == []


@pytest.mark.parametrize("mutate", [lambda d: d.update(extra=1), lambda d: d.update(outcome="success"),
                                    lambda d: d["steps"][0].update(status="maybe"),
                                    lambda d: d["approval"].update(approved_by=""), lambda d: d.pop("run_id")])
def test_schema_rejects_bad_documents(mutate):
    doc = json.loads(TeamSession.model_validate(session()).model_dump_json())
    mutate(doc)
    assert schema_errors(doc) != []
