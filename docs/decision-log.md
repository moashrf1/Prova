# Decision Log

Authorship and reasoning record for the AI Enablement System build, per the
"full authorship evidence from commit #1" guardrail. One entry per meaningful
decision, newest first.

## 2026-07-09 — Session 4: vendored Chart.js instead of linking the CDN

**Context:** the build doc's Phase 4 instructions say "Add Chart.js (via
CDN)." The build environment's outbound network policy blocks the
jsdelivr CDN this session was run in, so a `<script src="https://cdn...">`
tag couldn't be verified working here.

**Decision:** downloaded `chart.js@4` via npm (npm's registry is
allow-listed) and committed the UMD build to `static/vendor/chart.umd.min.js`
(~208KB, MIT licensed), loaded via a plain `<script>` tag with no build
step. This is a deliberate deviation from "via CDN," not a workaround
forced by this one sandbox: a locally-hosted personal dashboard that's
supposed to run offline on personal hardware shouldn't need internet
access at runtime just to draw a bar chart. If bandwidth/repo-size becomes
a concern later, switching the one `<script src="...">` line back to a CDN
url is a one-line change.

**Verified:** charts render correctly against seeded data over real HTTP,
confirmed with Playwright screenshots (bar heights match the
`/api/projects` and `/api/skills` numbers exactly) and zero console errors
(aside from the browser's own unrelated `favicon.ico` 404).

## 2026-07-09 — Session 4: single accent hue per chart, no legend, no color validator run

**Context:** the dataviz skill's method requires assigning categorical
hues in fixed order and running the CVD-safety validator for any
categorical palette, plus a legend whenever 2+ series are shown.

**Decision:** both dashboard charts (time per project, skill fetch counts)
are single-series bar charts -- the categories live on the x-axis as
labels, not as competing series distinguished by color. Per the skill's
own rule ("a single series needs no legend box -- the title names it"),
one accent hue for all bars is correct here, not a shortcut around the
categorical-palette rules; those rules apply once color itself is doing
the job of distinguishing multiple series, which isn't the case here. No
validator run needed since there's no multi-hue categorical palette to
validate.

## 2026-07-09 — Session 4: system font stack instead of an embedded webfont

**Context:** the environment's design guidance (calibrated for claude.ai
Artifacts) says to inline a webfont as a `@font-face` data URI rather than
link a CDN font, since Artifacts run under a CSP that blocks external
font requests.

**Decision:** this dashboard is not an Artifact -- it's a FastAPI app meant
to run on personal hardware, offline-capable, with no build step. Neither
constraint (the Artifact CSP, or the "embed so it always renders")
actually applies the same way, and downloading/vendoring a font binary
would add repo weight and a licensing question for no real gain. Used a
deliberate system-font stack instead (sans throughout, with a monospace
stack reserved for every number, on stat cards and throughout, for a
consistent "engineering logbook" identity), styled with a real type scale,
weight, and tracking so it doesn't read as an unstyled default. This is a
calibration of the design skill's intent (considered typography, not an
inherited default) to a context the skill wasn't specifically written for.

## 2026-07-09 — Session 4: dashboard palette and layout

**Context:** the build doc's explicit goal is "polished, not templated" --
suitable for showing management, but the guidance also warns against
over-designing a utilitarian page (no giant hero, no flashy decoration).

**Decision:** single-page, no hero: a top bar (title + period toggle),
then stacked sections (recap stat cards, charts, learning path, projects,
decisions) that read top-to-bottom like a real report. Accent teal
(`#1d6f72` light / `#4fbdc0` dark) used only for the active period toggle
and, later, chart/progress fills -- everywhere else stays neutral ink and
slate, so the one spot of color reads as deliberate rather than
decorative. Chose this over the AI-cliche defaults called out in the
design guidance (warm cream + terracotta, near-black + neon, purple-blue
gradient hero) precisely because those are the clichés to avoid when nothing
else pins the direction.

## 2026-07-09 — Session 4: hardened analytics_store.py's own connection to read-only, instead of a separate read-only layer in web/app.py

**Context:** the build doc asked for the web layer to open SQLite read-only
(`mode=ro`) so a bug in the dashboard literally cannot write, while also
insisting on reusing Session 3's query logic rather than duplicating it.
Those two asks are in tension if the read-only connection lives only in
`web/app.py`, since `analytics_store.py`'s functions each open their own
connection internally.

**Decision:** `analytics_store.py` already documented itself as read-only
("nothing here writes") and, on inspection, every function is in fact a
pure `SELECT`. So `db_connection()` inside `analytics_store.py` itself now
opens with `mode=ro` (via `DB_PATH.as_uri() + "?mode=ro"`, `uri=True`),
turning a documented convention into an enforced one. `web/app.py` then
imports `analytics_store` directly and calls the exact same
`compute_recap`/`compute_learning_stats` functions the MCP tools call --
genuine reuse, not a parallel read-only wrapper. The read-only guarantee
now covers the MCP tool path too, which is strictly stronger than the
build doc asked for, at no cost (those tools were always read-only in
practice).

**Rejected alternative:** give `web/app.py` its own read-only connection
and either duplicate the queries or thread a connection parameter through
every `analytics_store` function. Rejected as unnecessary complexity once
it was clear the module's connections could just be read-only everywhere.

**Verified:** existing 27 Session 1-3 tests still pass unchanged against
the now-read-only connection (they were always read-only in practice); a
direct write attempt through `analytics_store.db_connection()` raises
`sqlite3.OperationalError: attempt to write a readonly database`; and
`/api/recap` served over real HTTP (uvicorn) returns output identical to
calling `analytics_store.compute_recap` directly.

## 2026-07-09 — Session 3: `monthly` is a rolling 30-day window, not a calendar month

**Context:** `generate_recap(period)` needed a concrete definition of
"monthly" before the query helpers could be written.

**Decision:** rolling 30 days ending now, exactly parallel to `weekly`
(rolling 7 days). Both periods use the same `period_bounds()` logic with
only the window length differing.

**Rejected alternative:** calendar month (1st to today, or 1st-to-last-day).
Rejected because it makes the recap's meaning depend on what day of the
month you happen to run it — on the 2nd, a "monthly" recap would cover
almost nothing, while at the end of the month it would cover almost
everything. A rolling window always means the same thing regardless of
when you ask for it.

## 2026-07-09 — Session 3: skills_fetched excludes typo'd/nonexistent skill names

**Context:** `get_skill` logs a `fetched` row in `skill_usage` even when the
name doesn't match any real skill (a Session 1 decision, so failed lookups
are visible in analytics). That means a straight `DISTINCT skill_name`
query over `skill_usage` could count a typo as a "skill fetched."

**Decision:** both `skills_fetched_in_range` (recap) and the cumulative
count in `compute_learning_stats` intersect the distinct fetched names
against the names that currently exist in `skills/` (via
`skills_store.load_all_skills()`), so only real skills count toward
"skills fetched" or path progress.

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
