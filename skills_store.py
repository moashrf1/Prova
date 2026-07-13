"""Reads skill markdown files and tracks usage in SQLite.

Hand-rolled rather than using the standalone `fastmcp` package's Skills
provider (fastmcp>=3.0, a different package from the `mcp` SDK's built-in
FastMCP class pinned by this project). The reader here is a few lines of
YAML-frontmatter parsing, and hand-rolling it keeps the progressive
disclosure boundary between `list_skills` (light) and `get_skill` (heavy)
fully visible and easy to measure, instead of delegating it to a
third-party provider.
"""

import json
import re
import sqlite3
from pathlib import Path

import yaml

import token_metrics

SKILLS_DIR = Path(__file__).parent / "skills"
DB_PATH = Path(__file__).parent / "data" / "enablement.db"

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row[1] == column for row in conn.execute(f"PRAGMA table_info({table})"))


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS skill_usage (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_name  TEXT NOT NULL,
                action      TEXT NOT NULL,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        # Additive migration: adds size columns without touching existing
        # rows (they stay NULL for history predating this instrumentation).
        # Session 6 -- see docs/decision-log.md for why this is additive
        # rather than a rebuild.
        if not _column_exists(conn, "skill_usage", "chars"):
            conn.execute("ALTER TABLE skill_usage ADD COLUMN chars INTEGER")
        if not _column_exists(conn, "skill_usage", "tokens_est"):
            conn.execute("ALTER TABLE skill_usage ADD COLUMN tokens_est INTEGER")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS library_snapshots (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                total_skills      INTEGER NOT NULL,
                total_chars       INTEGER NOT NULL,
                total_tokens_est  INTEGER NOT NULL,
                created_at        TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )


def log_usage(
    skill_name: str,
    action: str,
    chars: int | None = None,
    tokens_est: int | None = None,
) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO skill_usage (skill_name, action, chars, tokens_est) VALUES (?, ?, ?, ?)",
            (skill_name, action, chars, tokens_est),
        )


def measure_listing(skill: dict) -> tuple[int, int]:
    """Size of the metadata this one skill contributes to a list_skills call.

    Measured per-skill (not once for the whole list) so summing chars/
    tokens_est across a period's 'listed' rows reconstructs the true total
    metadata served, without double-counting or a separate "whole list"
    row shape.
    """
    metadata = {
        "name": skill["name"],
        "title": skill["title"],
        "description": skill["description"],
        "category": skill["category"],
        "path": skill["path"],
    }
    return token_metrics.measure(json.dumps(metadata))


def record_library_snapshot() -> None:
    """Snapshot the full library's size, but only if it changed.

    Called on server start. Keeps the baseline ("as if the whole library
    were loaded up front") auditable over time as skills are added,
    without writing a duplicate row every single startup.
    """
    skills = load_all_skills()
    total_chars = sum(len(skill["body"]) for skill in skills)
    total_tokens_est = token_metrics.estimate_tokens(total_chars)

    with sqlite3.connect(DB_PATH) as conn:
        latest = conn.execute(
            "SELECT total_skills, total_chars, total_tokens_est "
            "FROM library_snapshots ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if latest == (len(skills), total_chars, total_tokens_est):
            return
        conn.execute(
            "INSERT INTO library_snapshots (total_skills, total_chars, total_tokens_est) "
            "VALUES (?, ?, ?)",
            (len(skills), total_chars, total_tokens_est),
        )


def _parse_skill_file(path: Path) -> dict:
    match = FRONTMATTER_RE.match(path.read_text())
    if not match:
        raise ValueError(f"{path.name} is missing YAML frontmatter")
    frontmatter, body = match.groups()
    meta = yaml.safe_load(frontmatter)
    meta["body"] = body.strip()
    return meta


def load_all_skills() -> list[dict]:
    return [_parse_skill_file(p) for p in sorted(SKILLS_DIR.glob("*.md"))]


def find_skill(skill_name: str) -> dict | None:
    for skill in load_all_skills():
        if skill["name"] == skill_name:
            return skill
    return None


def _skill_keyword_index() -> dict[str, set[str]]:
    """Distinguishing keywords per skill, for matching free text against
    skill relevance without an LLM or a tokenizer dependency -- deterministic
    keyword matching, consistent with token_metrics.py's chars/4 heuristic.

    Built from each skill's tags plus the words in its kebab-case name. A
    keyword shared across 2+ skills can't tell them apart, so it's dropped
    everywhere it appears -- this is what stops a word like "product"
    (shared by all three PM skills) or "ai" (shared by two technical ones)
    from producing a false-positive match.
    """
    skills = load_all_skills()
    raw: dict[str, set[str]] = {}
    for skill in skills:
        words = {w.lower() for w in skill.get("tags", []) if len(w) > 2}
        words.update(w.lower() for w in skill["name"].split("-") if len(w) > 2)
        raw[skill["name"]] = words

    owner_count: dict[str, int] = {}
    for words in raw.values():
        for word in words:
            owner_count[word] = owner_count.get(word, 0) + 1

    return {
        name: {word for word in words if owner_count[word] == 1}
        for name, words in raw.items()
    }


def classify_skills_in_text(text: str) -> list[str]:
    """Skill names whose distinguishing keywords appear as whole words in
    `text`. Requires at least 2 distinct keyword matches per skill, so one
    coincidental word can't trigger a false positive on its own.

    This is deliberately a lightweight signal for "this work referenced
    this skill's topic," not a claim that the skill's content was actually
    read -- get_skill's usage log remains the source of truth for that.
    """
    text_lower = text.lower()
    matched = []
    for name, keywords in _skill_keyword_index().items():
        if not keywords:
            continue
        hits = {kw for kw in keywords if re.search(rf"\b{re.escape(kw)}\b", text_lower)}
        if len(hits) >= 2:
            matched.append(name)
    return sorted(matched)
