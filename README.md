# AI Enablement System

An MCP server that gives an AI-assisted worker a personal skills library with
progressive disclosure: a lightweight listing of what's available, and full
teaching content loaded only for the skill actually needed. This is Session 1
of a larger system — see `docs/build-plan-session-1.md` for the full context
and `docs/decision-log.md` for the reasoning behind key choices.

## What's here

- `server.py` — the MCP server (FastMCP, from the `mcp` SDK). Exposes two
  tools: `list_skills` and `get_skill`.
- `skills_store.py` — reads skill markdown files from `skills/` and logs
  usage to SQLite.
- `skills/*.md` — one file per skill: YAML frontmatter (the lightweight
  metadata layer) + a markdown body (the full content, loaded on demand).
- `data/enablement.db` — SQLite database, `skill_usage` table only (created
  automatically on first run). Not checked into git.
- `docs/` — the build plan and the decision log.

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
