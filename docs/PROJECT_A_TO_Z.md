# Multi-Agent Copilot: the A-to-Z guide

This guide explains the whole project to someone who has never seen it. It uses plain language, and every technical
term is defined the first time it appears (the glossary in section 14 repeats them). Every number comes from a run
record, a log or a test run in this repository, with its source named. Anything not verified is marked **UNVERIFIED**.

**Contents**
1. [What this project is](#1-what-this-project-is)
2. [Origin and lineage](#2-origin-and-lineage)
3. [The core idea: HTTP 200 is not recovery](#3-the-core-idea-http-200-is-not-recovery)
4. [The system under test](#4-the-system-under-test)
5. [Repository map](#5-repository-map)
6. [The safety model](#6-the-safety-model)
7. [The experiments](#7-the-experiments)
8. [The agent team](#8-the-agent-team)
9. [One session, step by step](#9-one-session-step-by-step)
10. [Naming map (old to new)](#10-naming-map-old-to-new)
11. [How to run it](#11-how-to-run-it)
12. [Evidence and numbers](#12-evidence-and-numbers)
13. [Honest limits and what we must not claim](#13-honest-limits-and-what-we-must-not-claim)
14. [Glossary (A to Z)](#14-glossary-a-to-z)
15. [Likely faculty questions](#15-likely-faculty-questions)
16. [Where to read next](#16-where-to-read-next)

---

## 1. What this project is

**Multi-Agent Copilot is a human-supervised multi-agent copilot for safe chaos engineering on the Eclipse SDV Fleet
Management Blueprint.**

In plain words: it is a tool that runs on one laptop next to a real, open-source fleet-management system for trucks.
It checks whether the vehicle data is really fresh, proposes a small controlled failure to test the system, waits for a
named person to approve it, causes that failure for a few seconds, undoes it, proves the system recovered, and writes a
report. **Chaos engineering** means testing a system by causing failures on purpose, in a controlled way, to find weak
spots before real outages do. The tool fixes nothing in the system it tests; it injects bounded faults, rolls them back
and reports.

The work is split between four software **agents** (separate components, each with one job) and one human:
a Monitor, a Planner, a human approval gate, a Safety Executor and an Analyst (section 8).

## 2. Origin and lineage

Multi-Agent Copilot began as the **ResiliencePilot SDV** entry for the **Bosch Hackathon 2026** (original repository:
https://github.com/Anshu-raj-co/ResiliencePilot). For the university project review we had little time, so instead of
starting from scratch we reused that tested project and extended it.

**What stayed the same:** the system under test, every safety rule, the three experiments, the evidence files under
`reports/day1/`, `reports/day2/` and `reports/guardrail-demo/` (recorded runs, never edited), the scoring, the
dashboard's existing panels, all ports and all container names, and the tagline.

**What changed:**
- **Names** (section 10): package, command-line tool, Compose project label and environment-variable prefix.
- **A new agent-team layer** (`backend/multiagent_copilot/agent_team/`) that wraps the existing code into five stages
  with a recorded trace (a log of every hand-off), plus `mcop team` commands, two read-only API routes and an
  "Agent trace" panel on the dashboard.
- **Two bug fixes found during the move to Windows:** a path check in dependency discovery, and the kill switch writing
  its stop file outside the repository when the folder name contains a space (`docs/rename-recon.md`, git log).

The hackathon submission record keeps the original name: `docs/TEAM_FORM_INFO.md`. Decision D-024 in
`docs/DECISIONS.md` records the rename.

## 3. The core idea: HTTP 200 is not recovery

*HTTP 200 is not recovery. Fresh data is.*

Trucks send **telemetry** (automatic measurements such as speed, fuel level and position) to a server. Fleet operators
read it through an **API** (Application Programming Interface: a fixed way for one program to ask another for data).
The usual health check asks the API something and looks for **HTTP 200** (the web status code for "OK").

Every answer from this API carries two timestamps:

| Field | Set by | Meaning |
|---|---|---|
| `createdDateTime` | the vehicle side (`fms-forwarder`) | when the data was produced: **the truth** |
| `receivedDateTime` | the server, at the moment you ask | "now" on the server: it always looks fresh |

When the vehicle side stops, `createdDateTime` freezes, `receivedDateTime` keeps ticking, and the API still answers
200. The data is **stale** (old and no longer refreshed) while every health check says "healthy". That is a **silent
failure** (a failure with no error message, so normal monitoring misses it).

We call data **STALE** when it is more than 5 seconds old or `createdDateTime` has not moved for 5 seconds
(`config/safety.json`, `stale_threshold_s: 5.0`), otherwise **FRESH**. We only call a system **recovered** when
`createdDateTime` advances again three times in a row, each fresh and with HTTP 200, after the fault is undone. HTTP 200
alone never counts.

In 16 of the 17 committed `telemetry_stall` run records the API answered HTTP 200 on 100 % of the polls during the fault
while the data froze; the 17th (`20261010T084842Z-baf896`) latched with an error and recorded no fault-window ratio
(`reports/day1/`, `reports/day2/`, `reports/guardrail-demo/`, `reports/team-sessions/`).

## 4. The system under test

We test the **Eclipse SDV Fleet Management Blueprint** (SDV: Software-Defined Vehicle; a blueprint is a ready-made
reference application). It is open source under Apache-2.0 and is included unchanged in
`Fleet Management/fleet-management/`, pinned at upstream commit `3d514ac72a`. We never edit its files; our changes go in
an override file, `config/compose/multiagent-copilot.override.yaml`.

It runs as 8 **containers** (isolated packages that each hold one program) started by **Docker Compose** (a tool that
starts a group of containers from one file) under the project name `multiagent-copilot`:

| Container | Role | Can we inject a fault? |
|---|---|---|
| `csv-provider` | fake truck: replays recorded signals | no (read-only) |
| `databroker` | Eclipse KUKSA: in-vehicle signal store | no |
| `fms-forwarder` | builds a vehicle status about once per second and stamps `createdDateTime` | **yes**: pause, or stop/start |
| `fms-zenoh-router` | Eclipse Zenoh: message router vehicle -> cloud | no |
| `fms-consumer` | writes statuses into the database | no |
| `influxDB` | time-series database (values stored with timestamps) | **yes**: stop/start |
| `fms-server` | the **rFMS API** (a truck-industry standard API) that we and fleet operators read | no (we only read it) |
| `grafana` | charts; not on the data path | no |

Data flow: `csv-provider -> databroker -> fms-forwarder -> fms-zenoh-router -> fms-consumer -> influxDB -> fms-server ->
our observer (HTTP GET /rfms/vehiclestatuses)`. If any link from the forwarder to the database breaks,
`createdDateTime` stops advancing while `fms-server` can keep answering 200. The verified map with evidence is in
`config/dependency_map.json`. Only `fms-forwarder` and `influxDB` are on the experiment allowlist
(`config/experiments.json`); everything else is read-only for us.

## 5. Repository map

| Path | What it holds |
|---|---|
| `README.md` | Front page: results, quick start, commands, the multi-agent section, safety model, limitations |
| `CLAUDE.md` | Engineering instructions and the non-negotiable safety rules (also used by AI coding sessions) |
| `Fleet Management/fleet-management/` | The vendored upstream blueprint (do not edit) |
| `config/` | `safety.json` (limits, Compose label), `experiments.json` (the allowlist), `dependency_map.json`, `ai.json` (local LLM settings), `profiles/` (tighten-only guardrail demo overlays), `compose/multiagent-copilot.override.yaml` |
| `contracts/` | **JSON Schemas** (strict rules for valid data): experiment request, observation, run record, `team_session.schema.json` |
| `backend/multiagent_copilot/` | The Python package. Observe: `sdv_adapter.py`, `telemetry.py`, `baseline.py`. Control: `safety.py`, `orchestrator.py`, `faults.py`, `guardrails.py`, `docker_cli.py`. Evidence: `evidence.py`. Analyse: `scoring.py`, `planner.py`, `findings.py`, `discover.py`, `insights.py`. Advise: `ai.py`. Interfaces: `__main__.py` (the `mcop` CLI), `api.py` + `static/dashboard.html`, `explainer.py`. Data-quality gate: `dq/` |
| `backend/multiagent_copilot/agent_team/` | The agent layer: `trace.py` (session models), `agents.py` (Monitor, Planner, Analyst), `executor_agent.py` (Safety Executor), `pipeline.py` (the five stages) |
| `backend/tests/` | Unit tests and live tests (`test_live.py`, run with `MCOP_LIVE=1`); team tests are `test_team_*.py` |
| `backend/data/` | Local runtime data, not committed: run records, baselines, `team_sessions/`, safety state, `run.lock` |
| `scripts/` | `stack-up.sh`, `stack-status.sh`, `stack-down.sh`, `kill-switch.sh`, `demo-day1.sh`, `build_scene_data.py`, deck builders |
| `reports/` | Committed evidence from real runs: `day1/`, `day2/`, `guardrail-demo/`, `team-sessions/` |
| `docs/` | This guide, design and architecture docs, decisions, demo scripts, recon, testing and safety reviews |

## 6. The safety model

Breaking things on purpose is only acceptable if it is safe. These rules are enforced in code and covered by tests:

- **Allowlist only.** Only the three predefined experiments in `config/experiments.json`, against their listed
  targets. Requests are validated strictly; unknown fields are rejected.
- **Sandbox only.** A target must have the exact allowlisted container name **and** the Docker Compose label
  `com.docker.compose.project = multiagent-copilot`. A same-named container from another project is refused. The label
  is set by `scripts/_compose.sh` and checked against `config/safety.json`; `backend/tests/test_label_consistency.py`
  fails if any copy differs.
- **One at a time, 30 s maximum.** A lock file allows one experiment across processes; total fault time including the
  watchdog grace is at most 30 s. A **watchdog** (an independent timer thread) forces rollback when time runs out.
- **Kill switch.** Emergency stop from the dashboard, `mcop stop`, or `scripts/kill-switch.sh`, which works even if the
  backend has crashed: it writes an `EMERGENCY_STOP` file and unpauses or starts the allowlisted targets.
- **Rollback always** (undoing the fault): on completion, cancel, timeout, lost observation, any error, or a
  **guardrail** trip (automatic limits on error rate, latency and **blast radius**: the set of containers an experiment
  may affect).
- **Strict recovery** as in section 3. If rollback or recovery cannot be proven, the tool **latches**
  (`LATCHED_UNSAFE`): no new experiments until a person checks the stack and runs a logged reset.
- **No `shell=True`, no free-form commands.** Docker is driven through one wrapper (`docker_cli.py`) with fixed
  arguments; nobody, including the AI, can supply a command string.
- **Deterministic safety path.** Stop, rollback, recovery checking and latching contain no LLM and no network call to
  an AI. The AI (local Ollama only) is advisory: no shell, no Docker, no credentials, no safety state. This is enforced by
  import-guard tests (`test_ai.py`, `test_team_import_guard.py`), because an AI that could influence the safety path
  could, in principle, keep a fault running or claim a recovery that did not happen.
- **No fake claims.** Never report an injection, recovery or measurement that was not observed.

## 7. The experiments

| Experiment | Injects | Bounds (catalogue max) | Predicted symptom | Measured (committed runs) |
|---|---|---|---|---|
| `telemetry_stall` | `docker pause fms-forwarder` (freeze; unpause loses nothing) | 30 s | `createdDateTime` stops, HTTP stays 200, data age grows past 5 s | HTTP 200 on every fault poll (16 of 17 records; one latched with an error); stale detected 4.768–5.332 s after injection in the full-window runs |
| `service_crash` | `docker stop` then `docker start fms-forwarder` | 15 s | same silent symptom; slower return than unpause | same silent symptom (Day 2, `reports/day2/`) |
| `dependency_failure` | `docker stop` then `docker start influxDB` | 15 s | HTTP 500 during the fault (visible), stored-data gap | visible 500s, but stale data served as HTTP 200 for about 21–24 s after the database returned in two runs (`reports/day2/findings.md`) |

All three share the global 30 s cap and the guardrails. There is no network-slowdown experiment: no proxy exists on the
data path, so we do not claim one (decision D-004).

## 8. The agent team

```
Monitor -> Planner -> HUMAN GATE -> Safety Executor -> Analyst
```

Four agents with distinct roles coordinated by an explicit Python pipeline that records every hand-off in a trace:

| Stage | Job | Uses the LLM? | Wraps |
|---|---|---|---|
| **Monitor** | Polls the API 6 times, judges each poll FRESH/STALE, checks a baseline exists. Unhealthy -> session refused, nothing planned or run | never | `RfmsObserver`, `FreshnessTracker`, stored baseline |
| **Planner** | Ranks the allowlisted experiments by rules (information value and risk). With `--ai` the local LLM may only reorder them | optional | `planner.plan`, `ai.ai_plan` |
| **Human gate** | A named person picks one proposal, types their name and `APPROVE` (or gives both `--experiment` and `--approved-by`) | human | `ApprovalRecord` |
| **Safety Executor** | Runs the approved experiment through the safety controller exactly like `mcop run`; never retries | never | `SafetyController`, `ExperimentRunner` |
| **Analyst** | Scores the run, derives findings, explains them; AI explanations must pass a **grounding check** (they must match the recorded evidence) | optional | `scoring`, `findings`, `ai.ai_analyse` |

**Why two agents never use the LLM.** The Monitor decides whether it is safe to proceed and the Safety Executor touches
Docker. Both must give the same answer every time and must not be talked into anything, so both are deterministic on
purpose. **The fallbacks:** if the LLM is off, slow, or returns something invalid, the Planner keeps the rule order and
the Analyst uses rule-based text; the trace records `status: fallback` and the `fallback_reason`.

**Import-guard separation.** Tests read the source code and fail if `agents.py` imports the safety controller,
orchestrator, faults, Docker wrapper or a shell; if `executor_agent.py` imports the AI client, `httpx` or `requests`; or
if `pipeline.py` imports anything beyond the agents and the trace. A second test starts a fresh Python and checks that
loading the executor never loads the AI module.

**What the trace records** (`contracts/team_session.schema.json`): per step the agent, its role, whether the LLM was
consulted, start and end time, a summary of inputs and outputs, the decision, evidence references, the status
(`ok`/`fallback`/`refused`/`error`) and any fallback reason; plus the approval (who, when, which experiment, and exactly
what they were shown), the run id and the outcome. Design details: `docs/MULTI_AGENT_DESIGN.md`.

## 9. One session, step by step

The committed session `reports/team-sessions/20261102T151952Z-8b5eaa.json` (readable `.txt` beside it; its run record
`20261102T151955Z-56a912.json` is in the same folder) was run on 2 November 2026 on Windows with:

```bash
.venv/Scripts/mcop team run --experiment telemetry_stall --approved-by "Anshu" --no-ai
```

`--no-ai` was used because Ollama was not running; the fallback is by design.

1. **Monitor** (2.65 s, ok): 6 of 6 polls FRESH, HTTP 200 6 of 6, `createdDateTime` advanced, max data age 0.78 s,
   baseline `baseline-20261102T150125Z` present. Decision: hand over to the Planner.
2. **Planner** (0.01 s, fallback, reason "AI disabled"): rule ranking 1. `dependency_failure`, 2. `service_crash`,
   3. `telemetry_stall`. `telemetry_stall` had been requested, so that proposal went to the gate.
3. **Human gate**: approved by Anshu at 15:19:55.252 UTC for `telemetry_stall` (planner rank 3). The record keeps the
   reasons, predicted symptoms and risks that were shown.
4. **Safety Executor** (30.11 s, ok): run `20261102T151955Z-56a912`, 25 s pause of `fms-forwarder`, COMPLETED. Fault
   verified; stale detected 5.332 s after injection; HTTP-200 ratio during the fault 1.0; rollback verified by the
   orchestrator; recovery verified 2.67 s after rollback.
5. **Analyst** (0.03 s, fallback, reason "AI disabled"): score 46.1; 8 findings over the 46 local run records, 2 of them
   cite this run.
6. **Outcome:** completed. Whole session 32.8 s.

## 10. Naming map (old to new)

| What | Old | New |
|---|---|---|
| Project name | ResiliencePilot SDV / ResiliencePilot | Multi-Agent Copilot |
| Python package | `resiliencepilot` | `multiagent_copilot` (`python -m multiagent_copilot`) |
| Compose project + safety label | `resiliencepilot-sdv` | `multiagent-copilot` |
| CLI command | `rp` | `mcop` |
| Environment variables | `RP_LIVE`, `RP_CONFIG_PROFILE`, `RP_APPROVER`, ... | `MCOP_LIVE`, `MCOP_CONFIG_PROFILE`, `MCOP_APPROVER`, ... |
| Repository | github.com/Anshu-raj-co/ResiliencePilot (unchanged, hackathon record) | github.com/Anshu-raj-co/Multi_Agent_AI_Copilot |

Committed evidence under `reports/day1/`, `reports/day2/` and `reports/guardrail-demo/` keeps the old names as recorded.

## 11. How to run it

Prerequisites: Docker Desktop (running), Python 3.13, Git; on Windows run the `.sh` scripts in Git Bash. Free local
ports: 8081, 8086, 3000, 7447, 55557.

```bash
git -c core.longpaths=true clone --recurse-submodules https://github.com/Anshu-raj-co/Multi_Agent_AI_Copilot.git
cd Multi_Agent_AI_Copilot
./scripts/stack-up.sh && ./scripts/stack-status.sh     # "all 8 services running"
cd backend
python3.13 -m venv .venv                               # Windows: py -3.13 -m venv .venv
.venv/Scripts/pip install -e ".[test]"                 # macOS/Linux: .venv/bin/...
.venv/Scripts/mcop status                              # must say READY
.venv/Scripts/mcop observe -n 6                        # FRESH, createdDateTime advancing
.venv/Scripts/mcop baseline -n 60                      # the Monitor needs a stored baseline
.venv/Scripts/mcop team run                            # one agent-team session; you approve it
.venv/Scripts/mcop team sessions                       # list sessions
.venv/Scripts/mcop team show <session_id>              # read one
.venv/Scripts/mcop serve                               # dashboard: http://127.0.0.1:8765/
.venv/Scripts/python -m pytest -q                      # unit tests
MCOP_LIVE=1 .venv/Scripts/python -m pytest -q          # plus live read-only tests (stack must be up)
cd .. && ./scripts/kill-switch.sh                      # emergency stop (then: mcop reset --operator NAME --note TEXT)
./scripts/stack-down.sh                                # stop the stack
```

Other commands: `mcop run`, `mcop stop`, `mcop reset`, `mcop runs`, `mcop show RUN_ID`, `mcop score`, `mcop plan`,
`mcop findings`, `mcop advise [--offline]`, `mcop deps`, `mcop discover`, `mcop show-baseline`, `mcop report`
(pass `--out reports/generated/...`; the default path overwrites a committed file). The scripted Day-1 demo:
`MCOP_APPROVER="<name>" ./scripts/demo-day1.sh`.

A fresh clone of the new repository has **not** been tested yet (**UNVERIFIED**); the steps above were run in the
working copy on Windows 11 on 2 November 2026.

## 12. Evidence and numbers

Only figures verified in run records, logs or test output from this repository:

| Figure | Value | Source |
|---|---|---|
| Committed run records (hackathon) | 37: Day 1 12, Day 2 21, guardrail demo 4 (`telemetry_stall` 16, `service_crash` 8, `dependency_failure` 13) | `reports/day1/`, `reports/day2/`, `reports/guardrail-demo/` |
| Committed team sessions | 2 (both completed `telemetry_stall`): `20261102T151952Z-8b5eaa` with `--no-ai`; `20261102T162147Z-d11fad` with `--ai` (Planner LLM answer accepted, Analyst LLM call timed out at 240 s and fell back) | `reports/team-sessions/` |
| Resilience Score medians, full-window Day-2 runs | `telemetry_stall` 62.2 (n=2, 60.9–63.5), `service_crash` 65.1 (n=5, 61.9–65.3), `dependency_failure` 61.6 (n=3, 57.5–63.2) | `mcop score --dir reports/day2` |
| Day-1 `telemetry_stall` median | 55.4 (n=6, 54.2–56.9) | `mcop score --dir reports/day1` |
| AI analyst evidence check | 1 of 7 explanations passed, in each of the two recorded real calls (`qwen2.5:7b`) | `reports/day2/ai_advice_qwen2.5-7b*.md`, `reports/day2/ai_calls/20261010T233726Z.json` |
| Unit tests (Windows, 2 Nov 2026) | 518 passed, 3 skipped | `pytest -q` |
| Live tests (Windows, 2 Nov 2026) | 521 passed | `MCOP_LIVE=1 pytest -q` |
| Day-1 demo (Windows, 2 Nov 2026) | exit 0 in 47 s: STALE while HTTP 200, 12 s run COMPLETED, kill-switch stop with recovery verified, refused run, reset | `scripts/demo-day1.sh` |

The Resilience Score (0–100) combines detection, recovery, data integrity and blast radius, with a penalty for polls
that were HTTP 200 but stale; parts that were not measured are left out (`docs/SCORING.md`).

## 13. Honest limits and what we must not claim

- It is **not** built on an agent framework such as LangGraph; the agents are coordinated by our own Python pipeline.
- It is **not autonomous**: a named human approves every run, and no flag skips that.
- It is **not self-healing**: it fixes nothing; it injects bounded faults, rolls them back and reports.
- It is **not production-ready** and **not safety-certified**; it runs only against a local sandbox.
- The local 7B model adds little: in the recorded real calls only 1 of 7 analyst explanations passed the evidence
  check. The deterministic layer carries the analysis.
- In the one committed team session with `--ai`, the Analyst's LLM call timed out at 240 s and fell back to rules; a
  team session in which the Analyst's AI answer was graded by the grounding check is **UNVERIFIED**.
- Faults are container pause/stop only; no network degradation. Small samples (n = 2–8 per experiment, hackathon runs).
- One simulated vehicle, one machine. The watchdog runs inside the backend process; a hard-killed backend leaves the
  fault until the kill switch or the next start-up undoes it.

## 14. Glossary (A to Z)

| Term | Meaning |
|---|---|
| Agent | A software component with one job in the pipeline (here: Monitor, Planner, Safety Executor, Analyst) |
| Allowlist | The fixed list of experiments and targets that may run; anything else is refused |
| API | A fixed way for one program to ask another for data |
| Approval record | The saved proof that a named person approved one experiment, with what they were shown |
| Baseline | Measurements taken when nothing is wrong, used for comparison |
| Blast radius | The set of containers an experiment is allowed to affect |
| Chaos engineering | Causing failures on purpose, in a controlled way, to find weak spots |
| Compose label | A tag Docker Compose puts on each container; ours is `multiagent-copilot` |
| Container | An isolated package holding one program and what it needs |
| Deterministic | Always the same output for the same input; no AI involved |
| Evidence record (run record) | The JSON file saved for each run with every poll and timing |
| Fallback | Using the rule-based answer when the LLM is off or its answer is rejected |
| Fault injection | Causing a failure on purpose |
| FRESH / STALE | Vehicle data at most / more than 5 s old (or not advancing) |
| Grounding check | Checking that an AI explanation matches the recorded evidence |
| Guardrail | An automatic limit that stops an experiment early |
| HTTP 200 / 500 | Web status codes: OK / server error |
| Human gate | The step where a named person approves, or nothing runs |
| Import guard | A test that fails if a module imports something it must not |
| Kill switch | Emergency stop that works even if the backend has crashed |
| Latch (LATCHED_UNSAFE) | A locked safety state that blocks experiments until a person resets it |
| LLM | Large Language Model: an AI that reads and writes text (here `qwen2.5:7b` on Ollama, local only) |
| Pipeline | A fixed chain of steps; here the five stages of a team session |
| rFMS | A truck-industry standard API for fleet data |
| Rollback | Undoing a fault |
| SDV | Software-Defined Vehicle |
| Silent failure | A failure with no error message, so monitoring misses it |
| Telemetry | Automatic measurements sent from a vehicle |
| Trace | The session file that records every hand-off between agents |
| Watchdog | An independent timer that forces rollback when time runs out |

## 15. Likely faculty questions

**Is this really multi-agent?** It has four agents with distinct roles, separate modules and enforced boundaries
(import guards), coordinated by an explicit pipeline with a recorded trace and a human gate. It is not a framework of
free-running, self-directed agents, and we do not claim that; only two agents can use an LLM, and both fall back to
rules.

**Why not LangGraph or another agent framework?** The safety path must be deterministic and auditable. A small explicit
pipeline was enough, easy to test, and keeps the safety controller in full control (D-025).

**What does the AI actually contribute?** Little, and we say so: the Planner's order matched the rules, and only 1 of 7
analyst explanations passed the evidence check. Its value here is showing that AI output is checked and can be rejected.

**Could the AI start or prolong a fault?** No. It has no shell, Docker, credentials or safety-state access; the Safety
Executor cannot even import the AI module (tested).

**What if the person approving makes a mistake?** They can only choose among allowlisted experiments; the safety
controller still validates the request, caps the duration, watches guardrails and rolls back.

**Is the data real?** Yes. The blueprint runs locally; every number comes from a recorded run, and the committed session
in section 9 is a real run.

**Why did you reuse a hackathon project?** Time was short. The lineage is disclosed in the README, this guide and D-024.

## 16. Where to read next

- [MULTI_AGENT_DESIGN.md](MULTI_AGENT_DESIGN.md): the agent team in detail
- [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md): components, run lifecycle, trust boundaries
- [DECISIONS.md](DECISIONS.md): every design decision, D-001 to D-025
- [demo/MULTI_AGENT_DEMO_SCRIPT.md](demo/MULTI_AGENT_DEMO_SCRIPT.md): the 3-minute demo
- [SCORING.md](SCORING.md): the Resilience Score formula
