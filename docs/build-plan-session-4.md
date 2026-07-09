# AI Enablement System — Master Build Document (Session 4)

Sessions 1–3 (skills layer, worklog capture, analytics) are complete,
tested, and documented. This session builds a read-only web dashboard to
visualize the accumulated data — aimed at a polished view suitable for
showing management.

## 0. Where we are

**Delivered (Sessions 1-3):** MCP server; `skills/` with progressive
disclosure; `skills_store.py`, `work_store.py`, `analytics_store.py`; tools
`list_skills`, `get_skill`, `log_work`, `log_decision`, `generate_recap`
(temporal weekly/monthly), `learning_stats` (cumulative, path-aware); tables
`skill_usage`, `projects`, `sessions`, `worklog`, `decisions`; 41 passing
tests (27 carried over, 14 new); README + decision log + per-session build
docs.

**Session 4 goal:** a web dashboard that reads the SQLite data and presents
it visually — recaps, project/time breakdowns, decisions log, and
learning-path progress. Read-only: the dashboard never writes to the
database; the MCP server remains the only write path.

## 1. Architecture decisions

### Stack: FastAPI backend + vanilla frontend + Chart.js

Chosen over Streamlit (rejected: templated-looking) and a React SPA
(rejected: over-engineered for a personal-scale read-only viewer). FastAPI
+ vanilla HTML/CSS/JS + Chart.js gives full control over the look, no build
tooling, and a clean upgrade path later.

### Read-only, and how it connects

`analytics_store.py`'s own connection helper now opens SQLite in `mode=ro`
(rather than adding a separate read-only layer in `web/app.py`), so the
guarantee is enforced at the connection level for both the MCP tool path
and the new web path, and `web/app.py` reuses the exact same tested query
functions instead of duplicating them. Three new store functions
(`project_rollups`, `recent_decisions`, `skill_usage_counts`) were added for
endpoints Session 3 didn't need, each with tests.

### Backend/frontend split

FastAPI (`web/app.py`) exposes JSON endpoints; a vanilla frontend
(`static/`, served via `StaticFiles`) consumes them. No shared state beyond
the HTTP calls.

## 2. API endpoints

All `GET`, all read-only, all reusing `analytics_store.py`:

- `/api/recap?period=weekly|monthly`
- `/api/learning-stats?path=<slug>`
- `/api/projects`
- `/api/decisions?limit=N`
- `/api/skills`

## 3. Frontend design

Design plan (per the artifact-design and dataviz skills, calibrated as a
utilitarian/professional dashboard, not an editorial page): accent teal
(`#1d6f72` light / `#4fbdc0` dark) used sparingly on the active toggle and
chart/progress fills; neutral surfaces and ink for everything else; system
font stack (no webfont CDN — this app is meant to run offline on personal
hardware); monospace reserved for every number. Single-page, no hero: top
bar → stat cards → charts → learning path → projects table → decisions
log.

## 4. Build plan (phased, with checkpoints)

1. Backend scaffold + `/api/recap`, verified against the MCP tool's own
   output; confirmed a write attempt through the read-only connection
   fails.
2. Remaining endpoints (`learning-stats`, `projects`, `decisions`,
   `skills`), each backed by a new tested store function.
3. Frontend scaffold + static serving: layout shell, palette, typography,
   the recap section wired (period toggle → stat cards).
4. Charts (Chart.js, vendored locally rather than via CDN — see the
   decision log) + learning-path progress + decisions log, all
   cross-checked against their endpoints' raw numbers.
5. Polish + docs: responsive fix (the path-progress fraction no longer
   wraps mid-phrase on narrow screens), dark mode verified, empty-state
   behavior verified against a fresh database, README updated, this doc
   saved.

## 5. Explicitly NOT in this session

- Any write capability in the web layer (read-only, always).
- Authentication / multi-user (personal, local-only for now).
- Multi-agent orchestration (the next major step after this).
- Calendar integration; other-people's learning paths.

## 6. After this session

With the dashboard done, the demo has a visible face for the eventual
proposal — numbers, charts, and the decisions/authorship trail all in one
view. The remaining major step is the multi-agent orchestration layer
(Skills / Worklog / Analytics as Claude Code subagents on top of the
existing tools), which deserves its own planning conversation.
