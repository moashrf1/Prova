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
