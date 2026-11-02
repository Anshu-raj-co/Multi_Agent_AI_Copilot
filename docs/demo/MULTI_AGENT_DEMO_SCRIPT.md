# Multi-agent copilot demo script (3 minutes)

One live team session on the real local stack: Monitor -> Planner -> HUMAN GATE -> Safety Executor -> Analyst.
The presenter approves it with their own name. Everything shown is measured live or read from recorded files; nothing is
simulated. Design: [../MULTI_AGENT_DESIGN.md](../MULTI_AGENT_DESIGN.md).

## Before presenting (not on screen)

Windows paths shown; use `.venv/bin/` on macOS/Linux. Run the `.sh` scripts in Git Bash.

```bash
./scripts/stack-up.sh && ./scripts/stack-status.sh          # "all 8 services running"
cd backend
.venv/Scripts/mcop status                                    # must be READY, emergency_stop_engaged false
.venv/Scripts/mcop serve &                                   # dashboard on http://127.0.0.1:8765/
curl -s -m 3 http://127.0.0.1:11434/api/tags >/dev/null && echo "Ollama up: use --ai" || echo "Ollama off: use --no-ai"
```
Browser: dashboard, scrolled so the top row and the **Agent trace** panel are both reachable. Terminal in `backend/`,
large font.

## Script

| Time | Screen | Voice-over |
|---|---|---|
| **0:00–0:20** · Problem | Dashboard top row: gauge green, **HTTP 200**, FRESH | "The fleet API answers HTTP 200. That does not prove the vehicle data is fresh. Our copilot tests that safely, with a human in charge." |
| **0:20–0:50** · Monitor | Terminal: `.venv/Scripts/mcop team run` (add `--ai` if Ollama is up). First live line **[Monitor] OK (deterministic)** with "6/6 FRESH … createdDateTime advanced: True … baseline" | "Four agents with distinct roles, joined by our own Python pipeline. The Monitor is deterministic: it polls the API six times through our telemetry verifier and checks a baseline exists. An unhealthy stack ends the session here." |
| **0:50–1:15** · Planner | **[Planner]** line, then *Proposals (ranked)* with reasons, predicted symptoms and risks | "The Planner ranks only allowlisted experiments by rules. The local LLM may reorder them, nothing more; if it is off or answers badly, the rule order is used and the trace says why." |
| **1:15–1:30** · Human gate | Type the number of **telemetry_stall**, your name, then `APPROVE`. Line **[HUMAN] approved by <name> at <time>** | "Nothing runs until a named person approves. There is no flag that skips this." |
| **1:30–2:10** · Executor + stale data | Switch to the dashboard: phase timeline *Fault active → Stale detected*; HTTP chip stays **200** while the gauge goes red | "The Safety Executor never uses an LLM. It calls the same safety controller as every other command: allowlist, one-run lock, watchdog, guardrails. Look: HTTP 200, and the data is frozen." |
| **2:10–2:30** · Rollback + verified recovery | Timeline *Rolling back → Recovered*; terminal **[Executor] OK** line: rollback verified, recovery verified after ~3 s | "Rollback is automatic, and recovery counts only when createdDateTime advances again three times, never because of HTTP 200." |
| **2:30–2:50** · Analyst | **[Analyst]** line: score, findings citing this run, any `rejected F…` AI answer; dashboard **Agent trace** panel with the five rows and LLM / deterministic badges | "The Analyst scores the run and explains the findings. AI answers that contradict the evidence are rejected and listed; in our recorded real calls only 1 of 7 passed." |
| **2:50–3:00** · Close | `.venv/Scripts/mcop team show <session_id>` | "Every hand-off is in the session trace. HTTP 200 is not recovery. Fresh data is." |

## If something fails

| Problem | What to do | What to say |
|---|---|---|
| Ollama is off or slow | Run `mcop team run --no-ai` | "The fallback is by design: the Planner and Analyst give rule-based output, and the trace records `fallback_reason`." |
| Docker is down / stack unhealthy | Show the saved session: `mcop team show 20261102T151952Z-8b5eaa`, file `reports/team-sessions/20261102T151952Z-8b5eaa.txt` | "This is a recorded real session from 2 Nov 2026; nothing is re-enacted." |
| Monitor refuses | Show the refused session and its reason (`mcop team sessions`, `mcop team show <id>`) | "That is the Monitor doing its job: no experiment on an unhealthy stack." |
| Dashboard problem | `mcop team show <session_id>` in the terminal | "Same trace, read from the session file." |
| Controller BUSY or LATCHED_UNSAFE | `mcop status`; after a human check, `mcop reset --operator <name> --note "..."` | "The Executor recorded the controller's refusal; it never retries." |
