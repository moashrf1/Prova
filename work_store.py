"""Worklog capture: projects, sessions, worklog entries, and decisions.

Extends the existing data/enablement.db (the skill_usage table, owned by
skills_store.py, is untouched). Every connection here enables
`PRAGMA foreign_keys = ON` explicitly -- SQLite disables FK enforcement
by default per-connection, so the relationships declared below (session
requires a real project, worklog/decisions require a real session) are
only real if every writer turns it on. See docs/decision-log.md.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "enablement.db"


@contextmanager
def db_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL UNIQUE,
                description TEXT,
                status      TEXT NOT NULL DEFAULT 'active',
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id  INTEGER NOT NULL REFERENCES projects(id),
                started_at  TEXT NOT NULL DEFAULT (datetime('now')),
                ended_at    TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS worklog (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  INTEGER NOT NULL REFERENCES sessions(id),
                tasks       TEXT NOT NULL,
                learnings   TEXT,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS decisions (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id           INTEGER NOT NULL REFERENCES sessions(id),
                decision             TEXT NOT NULL,
                reasoning            TEXT NOT NULL,
                rejected_alternative TEXT,
                created_at           TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
