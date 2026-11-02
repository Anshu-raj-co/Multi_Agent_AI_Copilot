# Docs cleanup proposal

Inventory of every file under `docs/` (2026-11-02). *Referenced by* is a text scan of README.md, CLAUDE.md, scripts/, backend code, tests and other docs (excluding this file and the rename recon). Deletion rule: only DELETE rows that nothing references and that are not protected are removed, with `git rm`. MERGE and anything uncertain stays.

| Path | Purpose | Referenced by | Verdict | Reason |
|---|---|---|---|---|
| `docs/AI_LAYER.md` | AI layer design and its recorded measurements | README.md, docs/DECISIONS.md, docs/coordination/HANDOFF.md, docs/demo/DAY2_DEMO_SCRIPT.md, docs/scene/index.html, scripts/build_scene_data.py, scripts/make_official_ppt.py | KEEP | referenced |
| `docs/ARCHITECTURE.md` | Detailed Day-1 architecture diagram | README.md, docs/ARCHITECTURE_OVERVIEW.md, docs/BRIEF.md, docs/PROJECT_EXPLAINED.md | KEEP | referenced |
| `docs/ARCHITECTURE_OVERVIEW.md` | One-page architecture (protected) | README.md, docs/ARCHITECTURE.md, docs/MULTI_AGENT_DESIGN.md, docs/PROJECT_A_TO_Z.md, docs/TEAM_FORM_INFO.md, docs/coordination/HANDOFF.md | KEEP | protected |
| `docs/BRIEF.md` | Original product brief with priority overrides (read first per CLAUDE.md) | CLAUDE.md | KEEP | referenced |
| `docs/DATA_QUALITY.md` | Data-quality gate (dq package) documentation | backend/multiagent_copilot/dq/__init__.py, backend/multiagent_copilot/dq/batch_engine.py, backend/multiagent_copilot/dq/cli.py, backend/multiagent_copilot/dq/generator.py, backend/multiagent_copilot/dq/normalizer.py, backend/multiagent_copilot/dq/report.py, backend/multiagent_copilot/dq/schema.py, backend/multiagent_copilot/dq/store.py, docs/coordination/HANDOFF.md, docs/dq/report.html | KEEP | referenced |
| `docs/DAY2_PLAN.md` | Day-2 plan (planning document, Day 2 completed) | docs/coordination/HANDOFF.md | KEEP | planning leftover, but HANDOFF.md references it; historical record |
| `docs/DECISIONS.md` | Decision log D-001 to D-025 (protected) | README.md, config/compose/multiagent-copilot.override.yaml, docs/BRIEF.md, docs/MULTI_AGENT_DESIGN.md, docs/PROJECT_A_TO_Z.md, docs/PROJECT_EXPLAINED.md, docs/coordination/HANDOFF.md, scripts/make_official_ppt.py, scripts/stack-up.sh | KEEP | protected |
| `docs/MULTI_AGENT_DESIGN.md` | Agent-team design (protected) | README.md, backend/multiagent_copilot/agent_team/__init__.py, docs/ARCHITECTURE.md, docs/ARCHITECTURE_OVERVIEW.md, docs/PROJECT_A_TO_Z.md, docs/PROJECT_EXPLAINED.md, docs/demo/MULTI_AGENT_DEMO_SCRIPT.md | KEEP | protected |
| `docs/PROJECT_A_TO_Z.md` | The A-to-Z guide (protected) | README.md, docs/PROJECT_EXPLAINED.md, docs/coordination/CURRENT_STATUS.md, docs/coordination/HANDOFF.md, scripts/make_official_ppt.py | KEEP | protected |
| `docs/PROJECT_EXPLAINED.md` | Day-1 plain-English guide, partly superseded by the A-to-Z guide | docs/coordination/HANDOFF.md | MERGE | Day-1 guide largely covered by the A-to-Z guide; still named in HANDOFF.md, so it stays (out-of-date lines fixed) |
| `docs/REQUIREMENTS_TRACE.md` | Requirement-by-requirement trace against the brief (dated snapshot) | docs/coordination/CURRENT_STATUS.md, docs/coordination/HANDOFF.md, scripts/make_official_ppt.py | KEEP | referenced |
| `docs/ROADMAP.md` | Roadmap and follow-ups (incl. safety-review follow-ups) | backend/multiagent_copilot/explainer.py, docs/BRIEF.md, docs/PROJECT_EXPLAINED.md, docs/coordination/TASK_BOARD.md, docs/demo/DAY1_DEMO.md | KEEP | referenced |
| `docs/SCORING.md` | Resilience Score formula | README.md, backend/multiagent_copilot/__main__.py, backend/multiagent_copilot/findings.py, backend/multiagent_copilot/scoring.py, backend/multiagent_copilot/static/dashboard.html, docs/DECISIONS.md, docs/PROJECT_A_TO_Z.md, docs/REQUIREMENTS_TRACE.md, docs/scene/index.html, scripts/make_official_ppt.py | KEEP | referenced |
| `docs/TEAM_FORM_INFO.md` | Hackathon submission record (protected) | README.md, docs/PROJECT_A_TO_Z.md, docs/REQUIREMENTS_TRACE.md, docs/coordination/HANDOFF.md | KEEP | protected |
| `docs/coordination/CURRENT_STATUS.md` | Verified status snapshot (read first per CLAUDE.md) | CLAUDE.md, docs/BRIEF.md, docs/PROJECT_EXPLAINED.md, docs/coordination/HANDOFF.md, scripts/make_official_ppt.py | KEEP | referenced |
| `docs/coordination/HANDOFF.md` | Session handoff log (read first per CLAUDE.md) | CLAUDE.md, docs/BRIEF.md, docs/PROJECT_EXPLAINED.md | KEEP | referenced |
| `docs/coordination/TASK_BOARD.md` | Team roles and task board | docs/BRIEF.md | KEEP | referenced |
| `docs/demo/DAY1_DEMO.md` | How to run the Day-1 scripted demo | docs/PROJECT_EXPLAINED.md, docs/coordination/TASK_BOARD.md | KEEP | referenced |
| `docs/demo/DAY1_REPORT.md` | Day-1 judge report built from recorded runs | README.md, docs/DAY2_PLAN.md, docs/PROJECT_EXPLAINED.md, docs/coordination/HANDOFF.md, scripts/demo-day1.sh | KEEP | referenced |
| `docs/demo/DAY2_DEMO_SCRIPT.md` | Day-2 3-minute demo script | README.md, docs/TEAM_FORM_INFO.md, docs/coordination/HANDOFF.md, docs/demo/VIDEO_SCRIPT.md, scripts/make_official_ppt.py | KEEP | referenced |
| `docs/demo/MULTI_AGENT_DEMO_SCRIPT.md` | Multi-agent 3-minute demo script (protected) | README.md, docs/MULTI_AGENT_DESIGN.md, docs/PROJECT_A_TO_Z.md | KEEP | protected |
| `docs/demo/VIDEO_SCRIPT.md` | 2-minute submission video script incl. data-quality section | docs/coordination/HANDOFF.md, scripts/make_ppt.py | KEEP | referenced |
| `docs/demo/dashboard-after-kill.png` | Real-run dashboard screenshot after a kill switch | nothing | KEEP | unreferenced but a named real-run artefact; unsure, so kept |
| `docs/demo/dashboard-day2.png` | README dashboard screenshot (real run) | README.md, docs/TEAM_FORM_INFO.md, docs/coordination/HANDOFF.md, scripts/make_official_ppt.py | KEEP | referenced |
| `docs/demo/dashboard-stale.png` | Dashboard screenshot during a stale fault (real run) | scripts/make_official_ppt.py | KEEP | referenced |
| `docs/demo/day1-demo-run.log` | Recorded output of a real Day-1 demo run | docs/demo/DAY1_DEMO.md, docs/demo/DAY1_REPORT.md | KEEP | referenced |
| `docs/demo/explainer-chart.png` | Explainer page chart screenshot | docs/coordination/HANDOFF.md, scripts/make_official_ppt.py | KEEP | referenced |
| `docs/dq/report.html` | Generated sample data-quality report | backend/multiagent_copilot/dq/cli.py, docs/DATA_QUALITY.md, docs/coordination/HANDOFF.md, docs/demo/VIDEO_SCRIPT.md | KEEP | referenced |
| `docs/recon.md` | Phase-0 reconnaissance of the blueprint (verified facts) | README.md, backend/multiagent_copilot/dq/generator.py, docs/ARCHITECTURE.md, docs/BRIEF.md, docs/DAY2_PLAN.md, docs/PROJECT_A_TO_Z.md, docs/PROJECT_EXPLAINED.md, docs/coordination/HANDOFF.md, docs/coordination/TASK_BOARD.md, docs/testing/TESTING.md | KEEP | referenced |
| `docs/rename-recon.md` | Rename recon record (protected) | docs/PROJECT_A_TO_Z.md | KEEP | protected |
| `docs/scene/index.html` | Offline 3D replay of committed runs (generated data block) | docs/coordination/HANDOFF.md, docs/demo/VIDEO_SCRIPT.md, scripts/build_scene_data.py, scripts/make_official_ppt.py, scripts/make_ppt.py | KEEP | referenced |
| `docs/scene/screenshots/.png` | Replay-page screenshot | nothing | DELETE | unnamed duplicate-subject screenshot (accidental save: no filename), referenced by nothing |
| `docs/scene/screenshots/layout-retina-2x-1000x540.png` | Replay-page screenshot | nothing | KEEP | unreferenced but a named real-run artefact; unsure, so kept |
| `docs/scene/screenshots/layout-retina-2x-1280x800.png` | Replay-page screenshot | scripts/make_official_ppt.py | KEEP | referenced |
| `docs/scene/screenshots/m1-booth-inspector.png` | Replay-page screenshot | docs/coordination/HANDOFF.md (by pattern screenshots/m1-*) | KEEP | referenced |
| `docs/scene/screenshots/m1-dependency-failure-http500-t9.png` | Replay-page screenshot | scripts/make_official_ppt.py | KEEP | referenced |
| `docs/scene/screenshots/m1-guardrail-error-rate-t2.png` | Replay-page screenshot | docs/coordination/HANDOFF.md (by pattern screenshots/m1-*) | KEEP | referenced |
| `docs/scene/screenshots/m1-kill-switch-run-t14.png` | Replay-page screenshot | docs/coordination/HANDOFF.md (by pattern screenshots/m1-*) | KEEP | referenced |
| `docs/scene/screenshots/m1-telemetry-stall-t9.png` | Replay-page screenshot | docs/coordination/HANDOFF.md (by pattern screenshots/m1-*) | KEEP | referenced |
| `docs/scene/screenshots/m2-booth.png` | Replay-page screenshot | docs/coordination/HANDOFF.md (by pattern screenshots/m2-*) | KEEP | referenced |
| `docs/scene/screenshots/m2-building-fms-forwarder.png` | Replay-page screenshot | scripts/make_official_ppt.py | KEEP | referenced |
| `docs/scene/screenshots/m2-building-influxDB-datagap.png` | Replay-page screenshot | docs/coordination/HANDOFF.md (by pattern screenshots/m2-*) | KEEP | referenced |
| `docs/scene/screenshots/m2-hover-fms-server.png` | Replay-page screenshot | docs/coordination/HANDOFF.md (by pattern screenshots/m2-*) | KEEP | referenced |
| `docs/scene/screenshots/m2-packet.png` | Replay-page screenshot | docs/coordination/HANDOFF.md (by pattern screenshots/m2-*) | KEEP | referenced |
| `docs/scene/screenshots/m2-phone-390px.png` | Replay-page screenshot | docs/coordination/HANDOFF.md (by pattern screenshots/m2-*) | KEEP | referenced |
| `docs/scene/screenshots/m2-road-forwarder-router.png` | Replay-page screenshot | scripts/make_official_ppt.py | KEEP | referenced |
| `docs/scene/screenshots/m2-tolerances-ai.png` | Replay-page screenshot | docs/coordination/HANDOFF.md (by pattern screenshots/m2-*) | KEEP | referenced |
| `docs/scene/screenshots/m2-truck.png` | Replay-page screenshot | docs/coordination/HANDOFF.md (by pattern screenshots/m2-*) | KEEP | referenced |
| `docs/scene/screenshots/m3-ai-governance-tab.png` | Replay-page screenshot | docs/coordination/HANDOFF.md (by pattern screenshots/m3-*) | KEEP | referenced |
| `docs/scene/screenshots/m3-dependency-failure-http500-graph.png` | Replay-page screenshot | docs/coordination/HANDOFF.md (by pattern screenshots/m3-*) | KEEP | referenced |
| `docs/scene/screenshots/m3-findings-score-tab.png` | Replay-page screenshot | scripts/make_official_ppt.py | KEEP | referenced |
| `docs/scene/screenshots/m3-hud-impact-graph-gauges.png` | Replay-page screenshot | scripts/make_official_ppt.py | KEEP | referenced |
| `docs/scene/screenshots/m4-tour-step1.png` | Replay-page screenshot | docs/coordination/HANDOFF.md (by pattern screenshots/m4-*) | KEEP | referenced |
| `docs/scene/screenshots/m4-tour-step2.png` | Replay-page screenshot | docs/coordination/HANDOFF.md (by pattern screenshots/m4-*) | KEEP | referenced |
| `docs/scene/screenshots/m4-tour-step3-retina-1000x540.png` | Replay-page screenshot | docs/coordination/HANDOFF.md (by pattern screenshots/m4-*) | KEEP | referenced |
| `docs/scene/screenshots/m4-tour-step3.png` | Replay-page screenshot | docs/coordination/HANDOFF.md (by pattern screenshots/m4-*) | KEEP | referenced |
| `docs/scene/screenshots/m4-tour-step4.png` | Replay-page screenshot | docs/coordination/HANDOFF.md (by pattern screenshots/m4-*) | KEEP | referenced |
| `docs/scene/screenshots/m4-tour-step5.png` | Replay-page screenshot | docs/coordination/HANDOFF.md (by pattern screenshots/m4-*) | KEEP | referenced |
| `docs/scene/screenshots/m4-tour-step6.png` | Replay-page screenshot | scripts/make_official_ppt.py | KEEP | referenced |
| `docs/scene/three.r160.min.js` | Vendored three.js (MIT) used by the replay page | docs/TEAM_FORM_INFO.md, docs/coordination/HANDOFF.md, docs/scene/index.html, scripts/build_scene_data.py, scripts/make_official_ppt.py | KEEP | referenced |
| `docs/submission/ deck 1 (.pptx; file name keeps the hackathon name)` | Hackathon submission deck (binary, kept as submitted) | docs/coordination/HANDOFF.md, scripts/make_ppt.py | KEEP | referenced |
| `docs/submission/ deck 2 (.pptx; file name keeps the hackathon name)` | Hackathon submission deck (binary, kept as submitted) | scripts/make_official_ppt.py | KEEP | referenced |
| `docs/testing/SAFETY_REVIEW.md` | Independent safety reviews (safety document, protected) | README.md, backend/tests/test_safety.py, docs/PROJECT_EXPLAINED.md, docs/coordination/HANDOFF.md, docs/demo/DAY1_DEMO.md, docs/demo/DAY1_REPORT.md | KEEP | protected |
| `docs/testing/TESTING.md` | Test strategy and recorded test results | README.md, docs/PROJECT_EXPLAINED.md | KEEP | referenced |

Totals: 64 files; KEEP 62, MERGE 1, DELETE 1.
