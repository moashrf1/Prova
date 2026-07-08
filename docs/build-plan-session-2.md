# AI Enablement System — Master Build Document (Session 2)

Session 1 (the skills layer) is complete, tested, and documented. This
session builds worklog capture: the four data tables and the tools that
write to them.

## 0. Where we are

Session 1 delivered: the MCP server foundation, `skills/` markdown files
with progressive disclosure, `skills_store.py`, the `list_skills` and
`get_skill` tools, the `skill_usage` tracking table, a README, a decision
log, and a passing pytest suite.

Session 2 goal: capture work automatically. Build the `projects`,
`sessions`, `worklog`, and `decisions` tables and the tools that populate
them. Time is derived, never entered by hand.

## 1. The schema

Four tables, extending the existing `data/enablement.db`, added without
modifying or dropping `skill_usage`:

```sql
CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    status      TEXT NOT NULL DEFAULT 'active',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL REFERENCES projects(id),
    started_at  TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at    TEXT
);

CREATE TABLE IF NOT EXISTS worklog (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES sessions(id),
    tasks       TEXT NOT NULL,
    learnings   TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS decisions (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id           INTEGER NOT NULL REFERENCES sessions(id),
    decision             TEXT NOT NULL,
    reasoning            TEXT NOT NULL,
    rejected_alternative TEXT,
    created_at           TEXT NOT NULL DEFAULT (datetime('now'))
);
```

Relationships: `projects (1) ──< sessions (1) ──< worklog` and
`sessions (1) ──< decisions`. One project has many sessions; one session has
one worklog entry and many decisions.

SQLite disables foreign-key enforcement by default per-connection —
`PRAGMA foreign_keys = ON` is required on every connection to make the
relationships real rather than decorative.

## 2. Tools

- **`log_work(project_name, tasks, learnings=None)`** — end-of-session
  summary. Auto-creates the project if new (reuse via the `UNIQUE`
  constraint). Opens/reuses the session, writes the worklog row, closes the
  session.
- **`log_decision(decision, reasoning, rejected_alternative=None, project_name)`**
  — records one decision at the moment it's made, linked to the current
  session, without closing it.

### Session handling

Chosen: implicit sessions — `log_decision` opens/reuses a session without
closing it; `log_work` opens/reuses a session, writes its one worklog row,
and closes it. See `docs/decision-log.md` for the full rationale versus
explicit `start_session`/`end_session` tools.

## 3. Build plan (phased, with checkpoints)

1. Extend the data layer: four tables + FK enforcement.
2. Project + session helpers (`get_or_create_project`,
   `get_or_create_open_session`, `close_session`).
3. `log_work` tool.
4. `log_decision` tool.
5. Tests + documentation.

## 4. Explicitly NOT in this session

- Recaps and learning analytics (`generate_recap`, `learning_stats`).
- Multi-agent orchestration / Claude Code subagents.
- Career-path logic (the `path` field on skills stays stored but unused).
- Calendar/agenda integration.
