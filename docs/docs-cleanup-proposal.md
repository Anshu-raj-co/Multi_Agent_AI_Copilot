# Docs cleanup proposal

Inventory of `docs/` plus the two hackathon deck scripts (second pass, 2026-11-02). Goal: remove Day-1/Day-2
context-only material (day plans, status snapshots, requirement traces, scratch, outdated screenshots, hackathon decks
and their generator scripts) that the current project no longer needs.

**Rule.** A file is deleted (`git rm`) only if it is not protected and no live file references it. Protected: README.md,
CLAUDE.md, DECISIONS.md, TEAM_FORM_INFO.md, MULTI_AGENT_DESIGN.md, ARCHITECTURE_OVERVIEW.md, the A-to-Z guide,
MULTI_AGENT_DEMO_SCRIPT.md, safety docs, anything a test or code path reads, rename-recon.md, `reports/**` and
`Fleet Management/`. A *live* reference is one from code, tests, scripts, README/CLAUDE.md or a kept document that
points readers at the file today. Two cases do not count: references from files deleted in the same pass, and
entries in the dated session log `docs/coordination/HANDOFF.md`, which records what existed at the time and is kept
as history. Current-state pointers (for example in CURRENT_STATUS.md) are updated. Anything uncertain is kept.
Everything removed stays in git history.

| Path | Purpose | Live references | Verdict | Reason |
|---|---|---|---|---|
| `docs/AI_LAYER.md` | AI layer design and measurements | README.md, DECISIONS.md, scene page, build_scene_data.py | KEEP | referenced |
| `docs/ARCHITECTURE.md` | Detailed architecture | README.md, ARCHITECTURE_OVERVIEW.md, BRIEF.md | KEEP | referenced |
| `docs/ARCHITECTURE_OVERVIEW.md` | One-page architecture | README.md, MULTI_AGENT_DESIGN.md, A-to-Z | KEEP | protected |
| `docs/BRIEF.md` | Original product brief | CLAUDE.md | KEEP | referenced |
| `docs/DATA_QUALITY.md` | Data-quality gate docs | `dq/` package code | KEEP | code path |
| `docs/DAY2_PLAN.md` | Day-2 plan (done) | HANDOFF.md log only | DELETE | day plan; no live reference |
| `docs/DECISIONS.md` | Decision log | README.md, compose override, stack-up.sh | KEEP | protected |
| `docs/MULTI_AGENT_DESIGN.md` | Agent-team design | README.md, `agent_team/__init__.py` | KEEP | protected |
| `docs/PROJECT_A_TO_Z.md` | A-to-Z guide | README.md, CURRENT_STATUS.md | KEEP | protected |
| `docs/PROJECT_EXPLAINED.md` | Day-1 plain-English guide, superseded by the A-to-Z guide | HANDOFF.md log only | DELETE | superseded Day-1 guide; no live reference |
| `docs/REQUIREMENTS_TRACE.md` | Dated requirement trace against the hackathon brief | CURRENT_STATUS.md pointer (removed), deleted deck script | DELETE | requirement trace; pointer updated |
| `docs/ROADMAP.md` | Roadmap and follow-ups | `explainer.py`, BRIEF.md, TASK_BOARD.md | KEEP | code path |
| `docs/SCORING.md` | Resilience Score formula | README.md, `scoring.py`, dashboard | KEEP | code path |
| `docs/TEAM_FORM_INFO.md` | Hackathon submission record | README.md, A-to-Z | KEEP | protected |
| `docs/coordination/CURRENT_STATUS.md` | Verified status | CLAUDE.md | KEEP | CLAUDE.md workflow |
| `docs/coordination/HANDOFF.md` | Session handoff log | CLAUDE.md | KEEP | CLAUDE.md workflow |
| `docs/coordination/TASK_BOARD.md` | Day-1 role/task board | BRIEF.md | KEEP | referenced by the brief |
| `docs/demo/DAY1_DEMO.md` | Day-1 scripted demo | TASK_BOARD.md | KEEP | referenced |
| `docs/demo/DAY1_REPORT.md` | Day-1 report from recorded runs | README.md, `scripts/demo-day1.sh` | KEEP | referenced by a script |
| `docs/demo/DAY2_DEMO_SCRIPT.md` | Day-2 demo script | README.md, TEAM_FORM_INFO.md | KEEP | referenced by a protected file |
| `docs/demo/MULTI_AGENT_DEMO_SCRIPT.md` | Multi-agent demo script | README.md, MULTI_AGENT_DESIGN.md | KEEP | protected |
| `docs/demo/VIDEO_SCRIPT.md` | Hackathon submission video script | deleted deck script, HANDOFF.md log | DELETE | hackathon script; no live reference |
| `docs/demo/dashboard-after-kill.png` | Old dashboard screenshot | nothing | DELETE | outdated screenshot (pre-redesign UI) |
| `docs/demo/dashboard-day2.png` | Old dashboard screenshot | TEAM_FORM_INFO.md | KEEP | referenced by a protected file |
| `docs/demo/dashboard-stale.png` | Old dashboard screenshot | deleted deck script | DELETE | outdated screenshot |
| `docs/demo/explainer-chart.png` | Explainer chart screenshot | deleted deck script, HANDOFF.md log | DELETE | deck-only screenshot |
| `docs/demo/day1-demo-run.log` | Recorded Day-1 demo output | DAY1_DEMO.md, DAY1_REPORT.md | KEEP | recorded evidence |
| `docs/dq/report.html` | Sample data-quality report | `dq/cli.py`, DATA_QUALITY.md | KEEP | code path |
| `docs/recon.md` | Blueprint reconnaissance (verified facts) | README.md, `dq/generator.py` | KEEP | code path |
| `docs/rename-recon.md` | Rename recon record | A-to-Z | KEEP | protected |
| `docs/scene/index.html`, `three.r160.min.js` | Offline 3D replay of committed runs | `scripts/build_scene_data.py` | KEEP | referenced by a script |
| `docs/scene/screenshots/*.png` (26) | Screenshots of the replay page, which still exists | HANDOFF.md log | KEEP | not outdated; unsure, so kept |
| `docs/submission/` deck 1 and deck 2 (`.pptx`) | Hackathon submission decks (old name in the file names) | deleted deck scripts | DELETE | hackathon decks; the submitted copies remain in the original repository |
| `scripts/make_ppt.py` | Generator for hackathon deck 1 | `backend/pyproject.toml` extra `slides` (removed) | DELETE | hackathon deck script |
| `scripts/make_official_ppt.py` | Generator for hackathon deck 2 | nothing live | DELETE | hackathon deck script |
| `docs/testing/SAFETY_REVIEW.md` | Safety reviews | README.md, `test_safety.py` | KEEP | protected |
| `docs/testing/TESTING.md` | Test strategy and results | README.md | KEEP | referenced |
| `docs/docs-cleanup-proposal.md` | This table | README.md docs index | KEEP | record of the cleanup |

Deleted in this pass (11): DAY2_PLAN.md, PROJECT_EXPLAINED.md, REQUIREMENTS_TRACE.md, demo/VIDEO_SCRIPT.md,
demo/dashboard-after-kill.png, demo/dashboard-stale.png, demo/explainer-chart.png, the two submission decks,
scripts/make_ppt.py, scripts/make_official_ppt.py. The first pass removed one unnamed screenshot.
