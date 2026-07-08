"""Reads skill markdown files and tracks usage in SQLite.

Hand-rolled rather than using the standalone `fastmcp` package's Skills
provider (fastmcp>=3.0, a different package from the `mcp` SDK's built-in
FastMCP class pinned by this project). The reader here is a few lines of
YAML-frontmatter parsing, and hand-rolling it keeps the progressive
disclosure boundary between `list_skills` (light) and `get_skill` (heavy)
fully visible and easy to measure, instead of delegating it to a
third-party provider.
"""

import re
import sqlite3
from pathlib import Path

import yaml

SKILLS_DIR = Path(__file__).parent / "skills"
DB_PATH = Path(__file__).parent / "data" / "enablement.db"

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


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


def log_usage(skill_name: str, action: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO skill_usage (skill_name, action) VALUES (?, ?)",
            (skill_name, action),
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
