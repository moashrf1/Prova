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


def get_or_create_project(name: str) -> int:
    """Return the id of the project named `name`, creating it if new.

    Relies on the UNIQUE constraint on projects.name: INSERT OR IGNORE is a
    no-op if the name already exists, so this is safe to call every time a
    tool is invoked rather than requiring a separate "create project" step.
    """
    with db_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO projects (name) VALUES (?)", (name,))
        row = conn.execute(
            "SELECT id FROM projects WHERE name = ?", (name,)
        ).fetchone()
        return row[0]


def get_or_create_open_session(project_id: int) -> int:
    """Return the id of the project's currently-open session (ended_at IS NULL),
    creating one if none is open."""
    with db_connection() as conn:
        row = conn.execute(
            "SELECT id FROM sessions WHERE project_id = ? AND ended_at IS NULL "
            "ORDER BY id DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        if row is not None:
            return row[0]
        cursor = conn.execute(
            "INSERT INTO sessions (project_id) VALUES (?)", (project_id,)
        )
        return cursor.lastrowid


def close_session(session_id: int) -> None:
    with db_connection() as conn:
        conn.execute(
            "UPDATE sessions SET ended_at = datetime('now') WHERE id = ?",
            (session_id,),
        )


def log_work(project_name: str, tasks: str, learnings: str | None = None) -> dict:
    """Write the end-of-session worklog entry and close the session out.

    Opens (or reuses) the project's open session, writes the one worklog
    row it's allowed to have, then closes the session -- this is the
    "end of session" signal in the implicit session-handling scheme.
    """
    project_id = get_or_create_project(project_name)
    session_id = get_or_create_open_session(project_id)
    with db_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO worklog (session_id, tasks, learnings) VALUES (?, ?, ?)",
            (session_id, tasks, learnings),
        )
        worklog_id = cursor.lastrowid
    close_session(session_id)
    return {
        "project": project_name,
        "project_id": project_id,
        "session_id": session_id,
        "worklog_id": worklog_id,
    }


def log_decision(
    project_name: str,
    decision: str,
    reasoning: str,
    rejected_alternative: str | None = None,
) -> dict:
    """Record a single decision at the moment it's made.

    Opens (or reuses) the project's open session but does NOT close it --
    a session can hold many decisions before the log_work call that
    eventually closes it out.
    """
    project_id = get_or_create_project(project_name)
    session_id = get_or_create_open_session(project_id)
    with db_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO decisions (session_id, decision, reasoning, rejected_alternative) "
            "VALUES (?, ?, ?, ?)",
            (session_id, decision, reasoning, rejected_alternative),
        )
        decision_id = cursor.lastrowid
    return {
        "project": project_name,
        "project_id": project_id,
        "session_id": session_id,
        "decision_id": decision_id,
    }
