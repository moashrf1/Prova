"""Read-side queries over the accumulated skill_usage / work_store data.

Unlike skills_store.py and work_store.py, nothing here writes. Every
function is a pure query: given a date range (or nothing, for the
cumulative case), return structured data. The two public entry points
(compute_recap, compute_learning_stats) are what server.py's tools call;
everything else is a query helper kept small enough to unit test directly.

`monthly` is defined as a rolling 30-day window, not a calendar month --
see docs/decision-log.md. All timestamps in the database are UTC (SQLite's
`datetime('now')` default), so every comparison here uses
datetime.utcnow() to match.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

import skills_store

DB_PATH = Path(__file__).parent / "data" / "enablement.db"

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

PERIOD_WINDOWS = {
    "weekly": timedelta(days=7),
    "monthly": timedelta(days=30),
}


@contextmanager
def db_connection():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def _format(dt: datetime) -> str:
    return dt.strftime(TIMESTAMP_FORMAT)


def period_bounds(period: str, now: datetime | None = None) -> tuple[str, str]:
    if period not in PERIOD_WINDOWS:
        raise ValueError(f"Unknown period '{period}'; expected one of {list(PERIOD_WINDOWS)}")
    now = now or datetime.utcnow()
    start = now - PERIOD_WINDOWS[period]
    return _format(start), _format(now)


def sessions_in_range(start: str, end: str) -> list[dict]:
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT sessions.id, sessions.started_at, sessions.ended_at, projects.name
            FROM sessions
            JOIN projects ON projects.id = sessions.project_id
            WHERE sessions.started_at BETWEEN ? AND ?
            """,
            (start, end),
        ).fetchall()
    return [
        {"id": r[0], "started_at": r[1], "ended_at": r[2], "project": r[3]}
        for r in rows
    ]


def worklog_in_range(start: str, end: str) -> list[dict]:
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT worklog.tasks, worklog.learnings, worklog.created_at, projects.name
            FROM worklog
            JOIN sessions ON sessions.id = worklog.session_id
            JOIN projects ON projects.id = sessions.project_id
            WHERE worklog.created_at BETWEEN ? AND ?
            """,
            (start, end),
        ).fetchall()
    return [
        {"tasks": r[0], "learnings": r[1], "created_at": r[2], "project": r[3]}
        for r in rows
    ]


def decisions_in_range(start: str, end: str) -> list[dict]:
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT decisions.decision, decisions.reasoning,
                   decisions.rejected_alternative, decisions.created_at, projects.name
            FROM decisions
            JOIN sessions ON sessions.id = decisions.session_id
            JOIN projects ON projects.id = sessions.project_id
            WHERE decisions.created_at BETWEEN ? AND ?
            """,
            (start, end),
        ).fetchall()
    return [
        {
            "decision": r[0],
            "reasoning": r[1],
            "rejected_alternative": r[2],
            "created_at": r[3],
            "project": r[4],
        }
        for r in rows
    ]


def skills_fetched_in_range(start: str, end: str) -> list[str]:
    """Distinct skill names fetched in the range, restricted to skills that
    still exist -- a typo'd get_skill call logs a 'fetched' row too (see
    Session 1 decision log), but it isn't a skill anyone actually learned."""
    valid_names = {s["name"] for s in skills_store.load_all_skills()}
    with db_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT skill_name FROM skill_usage "
            "WHERE action = 'fetched' AND created_at BETWEEN ? AND ?",
            (start, end),
        ).fetchall()
    return sorted({r[0] for r in rows} & valid_names)


def _duration_seconds(started_at: str, ended_at: str) -> float:
    start_dt = datetime.strptime(started_at, TIMESTAMP_FORMAT)
    end_dt = datetime.strptime(ended_at, TIMESTAMP_FORMAT)
    return (end_dt - start_dt).total_seconds()


def compute_recap(period: str, now: datetime | None = None) -> dict:
    start, end = period_bounds(period, now)
    sessions = sessions_in_range(start, end)
    closed = [s for s in sessions if s["ended_at"] is not None]
    open_sessions = [s for s in sessions if s["ended_at"] is None]
    total_duration_seconds = sum(
        _duration_seconds(s["started_at"], s["ended_at"]) for s in closed
    )
    worklog = worklog_in_range(start, end)
    decisions = decisions_in_range(start, end)
    fetched_skills = skills_fetched_in_range(start, end)
    projects_touched = sorted({s["project"] for s in sessions})

    return {
        "period": period,
        "range_start": start,
        "range_end": end,
        "session_count": len(sessions),
        "open_session_count": len(open_sessions),
        "total_duration_seconds": total_duration_seconds,
        "projects_touched": projects_touched,
        "worklog_count": len(worklog),
        "worklog_entries": worklog,
        "decision_count": len(decisions),
        "decisions": decisions,
        "skills_fetched_count": len(fetched_skills),
        "skills_fetched": fetched_skills,
        "suggested_framing": (
            f"Summarize the {period} recap: {len(sessions)} session(s) across "
            f"{len(projects_touched)} project(s), {len(worklog)} worklog "
            f"entr{'y' if len(worklog) == 1 else 'ies'}, {len(decisions)} "
            f"decision(s) logged, {len(fetched_skills)} skill(s) fetched. "
            "Turn the tasks/learnings/decisions below into a short readable "
            "narrative -- don't just restate the numbers."
        ),
    }


def compute_learning_stats(path: str | None = None) -> dict:
    with db_connection() as conn:
        total_sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        total_decisions = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        fetched_names = {
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT skill_name FROM skill_usage WHERE action = 'fetched'"
            ).fetchall()
        }

    all_skills = skills_store.load_all_skills()
    valid_names = {s["name"] for s in all_skills}
    total_distinct_skills_fetched = len(fetched_names & valid_names)

    stats = {
        "total_sessions": total_sessions,
        "total_decisions": total_decisions,
        "total_distinct_skills_fetched": total_distinct_skills_fetched,
    }

    if path is not None:
        path_skill_names = {s["name"] for s in all_skills if s["path"] == path}
        fetched_on_path = sorted(path_skill_names & fetched_names)
        remaining_on_path = sorted(path_skill_names - fetched_names)
        stats["path"] = path
        stats["path_skill_total"] = len(path_skill_names)
        stats["path_skill_fetched_count"] = len(fetched_on_path)
        stats["path_skills_fetched"] = fetched_on_path
        stats["path_skills_remaining"] = remaining_on_path

    return stats
