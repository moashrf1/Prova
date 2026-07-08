# Decision Log

Authorship and reasoning record for the AI Enablement System build, per the
"full authorship evidence from commit #1" guardrail. One entry per meaningful
decision, newest first.

## 2026-07-08 — Session 2: implicit sessions, not start_session/end_session

**Context:** the schema says a session has exactly one worklog entry but many
decisions (`sessions (1) ──< worklog`, `sessions (1) ──< decisions`). Two
ways to manage session open/close: (a) explicit `start_session`/`end_session`
tools, or (b) implicit — `log_work`/`log_decision` open a session if none is
open, and something closes it.

**Decision:** implicit, with a specific refinement: `log_decision` opens (or
reuses) the project's currently-open session but never closes it; `log_work`
opens (or reuses) the session, writes the single worklog row, and closes it
(`ended_at = now`). This is the only implicit scheme consistent with the
schema's own cardinality — a session needs to stay open across multiple
decisions and close on the one worklog entry that summarizes it.

**Rejected alternative:** explicit `start_session`/`end_session` tools. More
precise in principle, but adds two tools the agent has to remember to call
correctly, and for a single-user demo the implicit scheme already produces a
real, non-trivial `ended_at - started_at` whenever decisions preceded the
`log_work` call — the "zero manual effort on timing" goal without the extra
API surface.

## 2026-07-08 — Session 2: enforce SQLite foreign keys explicitly

**Context:** SQLite disables FK enforcement by default per-connection, so
the `sessions.project_id`, `worklog.session_id`, and `decisions.session_id`
references would be decorative unless something turns it on.

**Decision:** every connection opened in `work_store.py` runs
`PRAGMA foreign_keys = ON` before use (centralized in one `db_connection()`
context manager, so it's impossible to open a connection there and forget
it). Verified by attempting to insert a session with a non-existent
`project_id` — it now raises `sqlite3.IntegrityError` instead of silently
succeeding.

**Rejected alternative:** leave FKs off for simplicity. Rejected because
these relationships were deliberately designed (§1 of the Session 2 build
doc) — leaving them unenforced would mean bad data (an orphaned session, a
worklog row pointing nowhere) fails silently instead of loudly, which
defeats the point of having the relationships at all.

## 2026-07-08 — Session 2: projects as a lookup table + separate decisions table

**Context:** why a `projects` table with a `UNIQUE` name instead of a free
text field on worklog, and why `decisions` as its own table instead of a
column on `worklog`.

**Decision:** kept exactly as designed in the Session 2 doc.
- `projects.name UNIQUE` plus auto-create-on-first-use (`INSERT OR IGNORE`
  then look up the id) prevents the same project splitting into variant
  spellings across reports, while still letting a worker just type a
  project name with no separate "create project" step.
- `decisions` is separate from `worklog` because a decision happens at a
  specific moment mid-session, not at the end-of-session summary point —
  giving it its own `created_at` (and optional `rejected_alternative`)
  preserves exactly when a deliberate human choice was made, which is the
  thing the authorship/IP evidence trail most needs to show.

## 2026-07-08 — Session 2: work_store.py owns its own DB init, not merged into skills_store.py

**Context:** the build doc says to add the four new tables "alongside the
existing skill_usage setup."

**Decision:** rather than merging everything into one shared init function,
`work_store.py` gets its own `DB_PATH`/`db_connection()`/`init_db()`, all
pointed at the same `data/enablement.db` file, and `server.py` calls both
`skills_store.init_db()` and `work_store.init_db()` at startup. Both use
`CREATE TABLE IF NOT EXISTS`, so calling either in either order is safe.
This keeps the two modules independent (no shared connection helper to
coordinate) and, concretely, avoids touching `skills_store.py` at all —
satisfying "do NOT modify... the existing skill_usage table" in the most
literal sense: the file that owns it is untouched.

## 2026-07-08 — Hand-rolled skill reader instead of fastmcp's Skills provider

**Context:** the build doc flagged that `fastmcp` (the standalone third-party
package, versions 3.0+) ships a built-in "Skills provider" and asked me to
evaluate it before hand-rolling a reader.

**Finding:** the pinned tech stack (`pip install "mcp[cli]"`) is the official
`mcp` SDK, whose `mcp.server.fastmcp.FastMCP` class is a different codebase
from the standalone `fastmcp` PyPI package that ships the Skills provider.
The installed `mcp` SDK (1.28.1) has no skill-loading feature at all.

**Decision:** hand-roll the reader (`skills_store.py`). Reasons:
- Adopting the Skills provider would mean swapping to a different framework
  than the one already decided, not just enabling a feature.
- The reader itself is a few lines of YAML-frontmatter parsing — a
  third-party provider buys negligible complexity reduction.
- Hand-rolling keeps the `list_skills` (light) / `get_skill` (heavy)
  boundary fully visible in our own code, which matters because that
  boundary is the exact thing this session needs to measure for the
  token-saving proposal.

## 2026-07-08 — Where usage logging happens

**Context:** `skill_usage` needs a row on every list and every fetch.

**Decision:** logging lives in `skills_store.py` (`log_usage`), called from
the thin tool wrappers in `server.py`. `get_skill` logs a `fetched` row even
when the name isn't found, so failed lookups are visible in analytics later
(e.g. "workers keep trying to fetch a skill that doesn't exist yet" is a
useful signal, not noise to discard).

## 2026-07-08 — Verifying without the MCP Inspector

**Context:** the build doc's checkpoints call for testing tools "with the MCP
Inspector," but Inspector is a browser UI and this session runs in a headless
remote container with no interactive browser.

**Decision:** verify each tool with the `mcp` Python client library directly
over stdio (`ClientSession` + `stdio_client`), which speaks the exact same
protocol Inspector uses under the hood. This gives the same pass/fail signal
("does the tool list, does it return the right thing") without requiring a
browser session.

## 2026-07-08 — Measuring the progressive-disclosure saving

**Context:** Phase 5's checkpoint asks to "compare the two output sizes and
record the difference" as the first metric for the proposal.

**Finding:** `list_skills` for all 6 skills (metadata only) is ~1.37KB.
Fetching all 6 full skill bodies would total ~4.74KB — about 3.5x more. In
practice a worker fetches the one or two skills relevant to their current
task, not all six, so the realistic per-task saving is larger than this
worst-case ratio suggests.
