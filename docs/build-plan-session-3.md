# AI Enablement System — Master Build Document (Session 3)

Sessions 1 (skills layer) and 2 (worklog capture) are complete, tested, and
documented. This session builds the read side: recaps and learning
analytics — the first tools that read the accumulated data instead of
writing to it.

## 0. Where we are

**Session 1 delivered:** MCP server foundation, `skills/` markdown files
with progressive disclosure, `skills_store.py`, `list_skills` / `get_skill`,
`skill_usage` tracking table, README, decision log, passing tests.

**Session 2 delivered:** `work_store.py`, the four data tables (`projects`,
`sessions`, `worklog`, `decisions`), FK enforcement on every connection,
implicit-session handling (`log_decision` opens/reuses a session without
closing; `log_work` opens/reuses, writes the one worklog row, closes it),
`log_work` and `log_decision` tools, 18 passing tests.

**Session 3 goal:** turn accumulated data into insight. Two tools:
- `generate_recap` — a temporal summary (weekly or monthly): computed
  numbers plus a natural-language narrative on top.
- `learning_stats` — cumulative progress, including progress toward a
  target career path. This session activates the `path` field stored on
  skills since Session 1.

## 1. Design decisions

### 1.1 `generate_recap` — computed numbers + narrative, temporal

Two layers: a computed layer (code queries the DB, computes exact
statistics — deterministic, testable) and a narrative layer (the agent
turns those numbers into a short natural-language recap; the tool itself
does not write prose).

**Period parameter:** `"weekly"` (rolling last 7 days) or `"monthly"`
(rolling last 30 days — a deliberate choice over calendar month; see
`docs/decision-log.md`). Purely temporal, not per-project.

**Computed layer includes:** session count and total derived time for the
period (still-open sessions excluded from the duration total but counted
separately), projects touched, worklog entries (count + content), decisions
(count + content), and skills fetched (count + names, from `skill_usage`
where `action = 'fetched'`).

### 1.2 `learning_stats` — cumulative, path-aware

Not temporal — measures all-time progress from the start: total distinct
skills fetched, total decisions logged, total sessions. With a target path
(e.g. `product-manager`), adds how many of that path's skills have been
fetched at least once out of the total tagged with that path.

### 1.3 The `path` field

This session is the first to read the `path` field stored on skills since
Session 1. Confirmed the six seed skills still carry it correctly: `null`
for the three technical skills, `product-manager` for the three product
ones.

## 2. Build plan (phased, with checkpoints)

1. Read helpers (`analytics_store.py`): query helpers for a date range —
   sessions + summed duration, projects touched, worklog, decisions, fetched
   skills. Decide and document the `monthly` definition.
2. `generate_recap` tool using the helpers.
3. `learning_stats` tool: cumulative + path progress.
4. Tests + documentation.

## 3. Explicitly NOT in this session

- Multi-agent orchestration / Claude Code subagents (next major step).
- Calendar/agenda integration.
- Admin-defined guided learning paths for other people.
- Any performance measurement of other people.

## 4. After this session

With recaps and learning analytics done, the read/write core of the system
is complete: skills in, work captured, insight out. The next major step is
the multi-agent orchestration layer — defining Skills/Worklog/Analytics
agents as Claude Code subagents on top of these tools, with the main
session as orchestrator.
