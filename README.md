# AI Enablement System

An MCP server that gives an AI-assisted worker a personal skills library with
progressive disclosure (Session 1), automatic worklog capture (Session 2) —
projects, sessions, decisions, and end-of-session summaries, with timing
always derived, never entered by hand — and recaps plus learning analytics
that read that accumulated data back (Session 3). See
`docs/build-plan-session-1.md` through `-session-3.md` for full context, and
`docs/decision-log.md` for the reasoning behind key choices.

## What's here

- `server.py` — the MCP server (FastMCP, from the `mcp` SDK). Exposes six
  tools: `list_skills`, `get_skill`, `log_work`, `log_decision`,
  `generate_recap`, `learning_stats`.
- `skills_store.py` — reads skill markdown files from `skills/` and logs
  usage to SQLite.
- `work_store.py` — projects/sessions/worklog/decisions: creation, lookup,
  and the session open/close logic behind `log_work` and `log_decision`.
- `analytics_store.py` — read-only queries over the accumulated data:
  temporal aggregates for `generate_recap`, cumulative/path-aware stats for
  `learning_stats`. Nothing here writes.
- `skills/*.md` — one file per skill: YAML frontmatter (the lightweight
  metadata layer) + a markdown body (the full content, loaded on demand).
- `data/enablement.db` — SQLite database: `skill_usage`, `projects`,
  `sessions`, `worklog`, `decisions` (created automatically on first run).
  Not checked into git.
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
