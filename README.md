# AI Enablement System

An MCP server that gives an AI-assisted worker a personal skills library with
progressive disclosure (Session 1), automatic worklog capture (Session 2) —
projects, sessions, decisions, and end-of-session summaries, with timing
always derived, never entered by hand — recaps plus learning analytics that
read that accumulated data back (Session 3), a read-only web dashboard that
visualizes all of it (Session 4), three specialized Claude Code subagents
that compose those tools into recurring workflows (Session 5), and automatic
token-savings measurement so normal daily use accumulates proposal evidence
with zero extra effort (Session 6). See `docs/build-plan-session-1.md`
through `-session-6.md` for full context, and `docs/decision-log.md` for the
reasoning behind key choices.

## What's here

- `server.py` — the MCP server (FastMCP, from the `mcp` SDK). Exposes seven
  tools: `list_skills`, `get_skill`, `log_work`, `log_decision`,
  `generate_recap`, `learning_stats`, `token_report`. **The only write path**
  onto the data.
- `token_metrics.py` — the single shared token-estimation heuristic
  (`chars // 4`) every call site routes through.
- `skills_store.py` — reads skill markdown files from `skills/`, logs usage
  (with size in chars/tokens_est) to SQLite, and snapshots the library's
  total size on server start (only when it's changed since the last
  snapshot).
- `work_store.py` — projects/sessions/worklog/decisions: creation, lookup,
  and the session open/close logic behind `log_work` and `log_decision`.
- `analytics_store.py` — read-only queries over the accumulated data
  (every connection opens SQLite in `mode=ro`): temporal aggregates for
  `generate_recap`, cumulative/path-aware stats for `learning_stats`,
  per-project rollups, recent decisions, skill usage counts, and the token
  savings math for `token_report`. Nothing here writes, and now nothing here
  *can*.
- `web/app.py` — a FastAPI app exposing the same `analytics_store` queries
  as JSON over HTTP, and serving `static/` (the dashboard). A second,
  read-only entry point onto `data/enablement.db` — it never writes.
- `static/` — the dashboard: `index.html`, `style.css`, `app.js`, and a
  locally vendored `vendor/chart.umd.min.js` (Chart.js, no CDN, no build
  step).
- `skills/*.md` — one file per skill: YAML frontmatter (the lightweight
  metadata layer) + a markdown body (the full content, loaded on demand).
- `.claude/agents/` — three subagents (`worklog-agent`, `skills-agent`,
  `analytics-agent`) that compose the MCP tools above into recurring
  workflows. See "Subagents" below.
- `data/enablement.db` — SQLite database: `skill_usage` (now with `chars`/
  `tokens_est` columns), `projects`, `sessions`, `worklog`, `decisions`,
  `library_snapshots` (created automatically on first run of the MCP
  server). Not checked into git.
- `docs/` — the build plans and the decision log.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running the server

```bash
python server.py
```

This starts the MCP server on stdio. Point an MCP client (Claude Code, the
MCP Inspector, or your own client) at it with:

```bash
mcp dev server.py   # MCP Inspector, if you have a browser available
```

## Running the dashboard

The MCP server must have run at least once so `data/enablement.db` exists
(the dashboard doesn't create it).

```bash
uvicorn web.app:app --reload
```

Then open <http://127.0.0.1:8000/>. The dashboard is **read-only** — it
opens the database in SQLite's `mode=ro`, so it cannot write even if there
were a bug; the MCP server above is the only write path. It's a second,
independent entry point onto the same `data/enablement.db` file: run both at
once, in separate terminals, with no coordination needed between them.

### Endpoints

All under `/api/`, all `GET`, all read-only, all reusing `analytics_store.py`:

| Endpoint | Returns |
|---|---|
| `/api/recap?period=weekly\|monthly` | Same numbers as the `generate_recap` MCP tool |
| `/api/learning-stats?path=<slug>` | Same as the `learning_stats` MCP tool (path optional) |
| `/api/projects` | Per-project session count, total time, last activity |
| `/api/decisions?limit=N` | Most recent N decisions (default 20) |
| `/api/skills` | Every skill with its all-time fetch count (0 if never fetched) |
| `/api/token-report?period=weekly\|monthly` | Same numbers as the `token_report` MCP tool (omit `period` for cumulative) |

### Dashboard sections

A prominent **token savings** card (headline percentage + a weekly/monthly/
all-time comparison chart) right at the top → recap stat cards (with the
weekly/monthly toggle) → activity charts (time per project, skill fetch
counts) → learning-path progress ("N of M `product-manager`-track skills
fetched", with fetched/remaining skills as chips) → a projects table → a
recent-decisions log (the visible authorship/IP trail). Every section
handles the empty-database case (sensible "nothing yet" messages, no
errors) and both light and dark mode.

## Tools

- **`list_skills()`** — returns `name`, `title`, `description`, `category`,
  `path` for every skill. No body content. This is the cheap call an agent
  makes to see what's available.
- **`get_skill(skill_name: str)`** — returns the full markdown body for one
  skill, or a polite message if the name doesn't match anything.

Both calls record a row in `skill_usage` (`listed` or `fetched`).

- **`log_work(project_name, tasks, learnings=None)`** — records the
  end-of-session summary. Auto-creates the project if the name is new
  (reuses it, unchanged, if it already exists — no duplicate rows).
  Opens or reuses the project's currently-open session, writes the one
  worklog row that session gets, then **closes the session**
  (`ended_at = now`).
- **`log_decision(project_name, decision, reasoning, rejected_alternative=None)`**
  — records one decision at the moment it's made. Same
  auto-create/reuse for the project and session as `log_work`, but does
  **not** close the session — a session can hold many decisions before
  the `log_work` call that eventually wraps it up.

### How time is derived

A session's `started_at` is set the moment it's first opened (by whichever
tool touches that project first — a decision or a worklog entry) and
`ended_at` is set only when `log_work` closes it. Nothing is ever typed in by
hand: call `log_decision` a few times while you work, then `log_work` once at
the end, and `ended_at − started_at` is a real elapsed-time measurement of
that stretch of work. Call `log_work` again later for the same project and
you get a new session, not a reopened one — each session is one bounded
stretch of work with exactly one worklog entry.

- **`generate_recap(period)`** — `period` is `"weekly"` (rolling last 7
  days) or `"monthly"` (rolling last 30 days — not a calendar month; see
  `docs/decision-log.md`). Purely temporal, not per-project. Returns
  computed numbers (session count, summed duration for closed sessions,
  still-open sessions counted separately, projects touched, worklog/decision
  counts and content, distinct skills fetched) plus a `suggested_framing`
  line. The tool does not write prose — it hands back clean structured data
  and lets the calling agent turn it into a short narrative.
- **`learning_stats(path=None)`** — cumulative, all-time, never windowed by
  date: total sessions, total decisions, total distinct skills fetched.
  Pass a career path (e.g. `"product-manager"`) to add fetched-vs-total
  progress for that path's skills, e.g. "2 of 3 PM-path skills fetched" —
  this is what finally puts the `path` field (stored on skills since
  Session 1) to use. Both this and `generate_recap` exclude
  fetched-but-nonexistent skill names (a typo'd `get_skill` call still logs
  a `fetched` row) from any "skills fetched" count.

### Temporal vs. cumulative

`generate_recap` answers "what happened lately" (a moving window);
`learning_stats` answers "how far have I come overall" (everything, ever).
The same accumulated tables feed both — the difference is entirely in the
date filter, not the data.

- **`token_report(period=None)`** — `period` is `"weekly"`, `"monthly"`, or
  omitted for all-time cumulative. Returns the actual content served
  (everything `list_skills`/`get_skill` sent out in that window) against the
  baseline (the whole library's size, from the most recent snapshot), plus
  the estimated saving in absolute tokens and percent. `generate_recap` also
  includes this as a `token_saving` block, computed for the same period, so
  a weekly recap naturally carries the number.

### What the token number actually measures — and what it doesn't

This is deliberately **not** "API tokens billed." The MCP server can't see
what the Claude client actually gets billed for — that happens in the
client/API layer, outside this process. What it *can* measure exactly is
the size of the content it serves, which is precisely the thing progressive
disclosure changes. So:

- **Actual**: the size of every `list_skills` response plus every skill
  body actually `get_skill`-fetched, in a window (or all-time).
- **Baseline**: the size of the *whole library*, as if it had all been
  loaded into context up front (the counterfactual the system replaces),
  taken from the most recent `library_snapshots` row.
- **Saving**: baseline − actual, in both absolute estimated tokens and
  percent.

Labeled everywhere as **"context content tokens (estimated)"** — read it as
"how much smaller the content this server sent was, versus sending
everything," not as a claim about your actual API bill. The estimate itself
is `tokens_est = chars // 4` (a standard rough heuristic for English text),
computed in one place (`token_metrics.py`) so it can be swapped for a real
tokenizer later without touching any call site — both `chars` and
`tokens_est` are stored everywhere, so the raw character counts survive
that kind of change. A real tokenizer dependency was deliberately skipped
for now: extra dependency, marginal accuracy gain on a metric that's
inherently *comparative* (both sides of the saving calculation use the
identical heuristic).

## Subagents

Three Claude Code subagents (`.claude/agents/*.md`) compose the MCP tools
above into recurring workflows, each scoped to only the tools its role
needs:

| Agent | Tools | Role |
|---|---|---|
| `worklog-agent` | `log_work`, `log_decision` | Turns a description of a work session into a worklog entry, logging any decisions *before* the closing `log_work` call (which ends the session) |
| `skills-agent` | `list_skills`, `get_skill` | Picks the right skill for a task via progressive disclosure — lists everything first, fetches only what's genuinely relevant |
| `analytics-agent` | `generate_recap`, `learning_stats` | Turns raw recap/stats data into a short readable answer — recaps are temporal, learning stats are cumulative, and it doesn't blur the two |

The main Claude Code session is the orchestrator: it reads each agent's
`description` and routes a request to the matching specialist(s), then
composes their results. For example:

```
"Log this work on project X, then show me a recap and my product-manager
track progress"
```

routes the logging half to `worklog-agent` and the recap/progress half to
`analytics-agent`, and the main session combines both replies into one
answer — each subagent does its work in its own context, so the detail of
those tool calls never floods the main conversation.

Try any of them directly by naming the agent: *"use the skills-agent to
help with this SQL problem"*, *"use the worklog-agent to log what I just
did"*, *"use the analytics-agent to show my weekly recap."*

## Adding a skill

Create a new file in `skills/` with the same frontmatter shape as the
existing ones:

```markdown
---
name: kebab-case-id
title: Human Readable Title
description: One to two sentences — this is the only part list_skills returns.
category: technical   # or: product
path: null             # or a career-path slug, e.g. product-manager
tags: [tag1, tag2]
---

# Full content goes here.
```

No code changes needed — the reader picks up any `.md` file in `skills/`.

## Tests

```bash
pytest
```

## Guardrails

Personal hardware/time/account only, zero company data, generic engine with
pluggable content, full authorship evidence from commit #1. See
`docs/build-plan-session-1.md` §0 for the complete list.
