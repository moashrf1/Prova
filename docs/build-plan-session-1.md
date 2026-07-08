# AI Enablement System — Master Build Document (Session 1)

How to use this document: Hand this entire file to Claude Code as the opening context for the project. It contains everything needed to build the foundation: architecture context, the skills database design, ready-to-use skill definitions, and a detailed phased build plan with checkpoints. Work through the phases in order, stopping at each checkpoint.

## 0. Context — what we are building and why

We are building the foundation of an AI Enablement System: an agentic system, built on an MCP server, that gives an AI-assisted worker a personal skills library, automatic worklog capture, and learning analytics. The system reduces token cost and ramp-up time while measurably improving the worker, not just speeding them up.

This session builds only the skills layer — the core mechanism that delivers the token-saving promise via progressive disclosure. Worklog capture, analytics, and the multi-agent orchestration come in later sessions.

### Guardrails (non-negotiable)

1. Personal hardware, personal time, personal account only.
2. Zero company data — all content is generic or synthetic.
3. Generic engine, pluggable content — the system is content-agnostic; company-specific skills are added only after official adoption.
4. Full authorship evidence from commit #1 — personal repo, timestamped commits, decision log.

### Tech stack (already decided)

- Language: Python.
- MCP framework: FastMCP (from the `mcp` SDK — `pip install "mcp[cli]"`).
- Storage: skills as markdown files + a lightweight SQLite tracking table (see §1).
- Later: multi-agent orchestration via Claude Code subagents; the main Claude Code session acts as orchestrator (subagents are one level deep and cannot spawn other subagents).

## 1. Skills database design (decision: files + tracking table)

Skills content lives in markdown files (flexible to edit, versioned in git). SQLite does not store skill content — it stores metadata and usage only, which powers learning analytics later.

### 1.1 Skill file format

Each skill is one markdown file in `skills/`, with YAML frontmatter (the lightweight layer) and a body (the full content loaded on demand).

Frontmatter fields:

- `name` — unique machine identifier (kebab-case). Used as the lookup key.
- `title` — human-readable title.
- `description` — ONE to TWO sentences. This is the only part loaded by `list_skills`. Keep it tight — this is the token-saving layer.
- `category` — `technical` or `product` (extensible).
- `path` — the career-path this skill belongs to, or `null` for general skills. Enables guided learning paths later (e.g. `product-manager`).
- `tags` — list for filtering.

### 1.2 SQLite tracking table

A single database file `data/enablement.db`. For this session, only ONE table is needed:

```sql
CREATE TABLE IF NOT EXISTS skill_usage (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name  TEXT NOT NULL,
    action      TEXT NOT NULL,           -- 'listed' or 'fetched'
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
```

This records every time a skill is listed or fetched. Later sessions add `projects`, `sessions`, `worklog`, and `decisions` tables (schema already designed — do NOT build them this session).

Note (technical): FastMCP 3.0 (released Jan 2026) includes a built-in "Skills provider". During Phase 4, briefly evaluate whether it simplifies loading skills before hand-rolling the file reader. If it adds complexity or hides the progressive-disclosure mechanism we want to measure, prefer the hand-rolled reader.

## 2. Initial skills

Six skill files in `skills/`: three technical (general, `path: null`) — `sql-query-optimization`, `prompting-patterns`, `rag-basics` — and three product-track (`path: product-manager`) — `product-discovery`, `prioritization-frameworks`, `stakeholder-communication`. See repository `skills/` directory for full content.

## 3. Build plan (phased, with checkpoints)

- **Phase 1** — Environment and repo: project structure, venv, `mcp[cli]` install, first commit.
- **Phase 2** — Minimal MCP server (Hello World): `FastMCP` instance, throwaway `ping` tool, verified then removed.
- **Phase 3** — Skills content: six markdown files with consistent frontmatter.
- **Phase 4** — Skill reader + `list_skills` tool: evaluate FastMCP's Skills provider vs. hand-rolled reader; return lightweight metadata only; log `listed` usage.
- **Phase 5** — `get_skill` tool: return full body by name; graceful not-found message; log `fetched` usage.

## 4. Explicitly NOT in this session

- The `projects`, `sessions`, `worklog`, `decisions` tables (designed, built later).
- Worklog capture, recaps, learning analytics.
- Multi-agent orchestration / Claude Code subagents.
- Career-path logic (the `path` field is stored now but not acted upon yet).
