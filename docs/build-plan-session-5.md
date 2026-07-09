# AI Enablement System — Master Build Document (Session 5)

Sessions 1–4 are complete (skills layer, worklog capture, analytics,
read-only dashboard). This session builds the multi-agent orchestration
layer — defining specialized subagents on top of the existing MCP tools,
with the main Claude Code session acting as orchestrator.

## 0. Where we are

**Delivered (Sessions 1-4):** MCP server with `list_skills`, `get_skill`,
`log_work`, `log_decision`, `generate_recap`, `learning_stats`; data layer
(`skill_usage`, `projects`, `sessions`, `worklog`, `decisions`); store
modules (`skills_store.py`, `work_store.py`, `analytics_store.py`);
read-only FastAPI dashboard; 41 passing tests; README, decision log,
per-session build docs.

**Session 5 goal:** compose the existing tools into three specialized
subagents so recurring multi-step workflows happen through a clean
division of labor instead of manual tool-by-tool invocation.

## 1. Design decisions

- **Claude Code subagents, not a hand-rolled orchestrator** — teaches the
  transferable pattern (scales to "each employee orchestrates their own
  subagents" if the project goes official) with the least engineering
  investment. A hand-rolled orchestrator is deferred until fine-grained
  routing/state control is actually needed.
- **Three peer subagents** (Skills / Worklog / Analytics), each scoped via
  `tools:` to only the MCP tools its role needs — least-privilege, and
  keeps the specialization that's the point of splitting them at all.
- **Build one agent fully before adding the others** — Worklog first,
  validated end-to-end, then Skills and Analytics under the same pattern.

## 2. Subagent mechanics (verified against official docs, not assumed)

Files live in `.claude/agents/*.md` (project-scoped). Only `name` and
`description` are required; `tools` is a comma-separated allowlist that
**inherits everything if omitted** (not "no tools"); individual MCP tools
are referenced as `mcp__<server>__<tool>`.

One delta from this doc's original assumption: subagents can spawn nested
subagents since Claude Code v2.1.172 (capped at depth 5) — not blocked at
one level. Doesn't affect this design since none of the three agents need
the `Agent` tool at all.

## 3. What was built

- `.claude/agents/worklog-agent.md` — `log_work` + `log_decision`.
  Enforces: log every decision before the closing `log_work` call (which
  ends the session).
- `.claude/agents/skills-agent.md` — `list_skills` + `get_skill`. Enforces
  progressive disclosure: list everything, fetch only what's relevant.
- `.claude/agents/analytics-agent.md` — `generate_recap` +
  `learning_stats`. Keeps temporal (recap) vs. cumulative (learning
  stats) distinct, and turns raw tool output into readable prose.

## 4. How each was validated

Not by reading the files and assuming they'd work — by real delegation
via a fresh `claude -p` process (a new `.claude/agents/` directory isn't
picked up by an already-running session) and checking actual SQLite state
or the `skill_usage` log afterward:

- **Worklog Agent**: decision row timestamped before the worklog row,
  session correctly closed.
- **Skills Agent**: all 6 skills `listed`, exactly 1 `fetched` for a real
  question.
- **Full orchestration**: one request touching both Worklog and Analytics
  agents produced a composed reply whose every number matched the
  database exactly.

## 5. Explicitly NOT in this session

- A hand-rolled Python orchestrator.
- Calendar integration; other-people's learning paths; performance
  measurement of others.
- New tools or schema changes — this session composes existing tools only.

## 6. After this session

The read/write/compose core of the system is complete: skills in, work
captured, insight out, and now a clean division of labor across
specialized agents. Further sessions would likely focus on refining agent
prompts based on real day-to-day use, or (per the original roadmap) moving
toward an official/team version if the personal demo proves out.
