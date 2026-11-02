"""Agent team: Monitor -> Planner -> HUMAN GATE -> Safety Executor -> Analyst (docs/MULTI_AGENT_DESIGN.md).

Deliberately imports nothing: importing one agent module must not load another (see tests/test_team_import_guard.py).
"""
