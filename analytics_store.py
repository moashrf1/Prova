"""Read-side queries over the accumulated skill_usage / work_store data.

Unlike skills_store.py and work_store.py, nothing here writes. Every
function is a pure query: given a date range (or nothing, for the
cumulative case), return structured data. The public entry points
(compute_recap, compute_learning_stats, project_rollups, recent_decisions,
skill_usage_counts) are what server.py's MCP tools and web/app.py's HTTP
endpoints both call -- one set of tested query logic, two entry points.

Every connection here opens in SQLite read-only mode (`mode=ro`): this
module documents itself as read-only, so the connection now enforces that
rather than just describing it -- a bug here literally cannot write,
which matters once the web dashboard (Session 4) is a second reader of
the same file the MCP server writes to.

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
import token_metrics

DB_PATH = Path(__file__).parent / "data" / "enablement.db"

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

PERIOD_WINDOWS = {
    "weekly": timedelta(days=7),
    "monthly": timedelta(days=30),
}


@contextmanager
def db_connection():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"{DB_PATH} does not exist yet -- run the MCP server (server.py) "
            "at least once to initialize it."
        )
    conn = sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True)
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


def project_rollups() -> list[dict]:
    """Per-project rollup for the dashboard's overview table: session count,
    total derived time (closed sessions only), and last activity timestamp
    (across both open and closed sessions)."""
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT projects.id, projects.name, projects.status,
                   sessions.id, sessions.started_at, sessions.ended_at
            FROM projects
            LEFT JOIN sessions ON sessions.project_id = projects.id
            """
        ).fetchall()

    projects: dict[int, dict] = {}
    for project_id, name, status, session_id, started_at, ended_at in rows:
        entry = projects.setdefault(
            project_id,
            {
                "name": name,
                "status": status,
                "session_count": 0,
                "total_duration_seconds": 0.0,
                "last_activity": None,
            },
        )
        if session_id is None:
            continue
        entry["session_count"] += 1
        if ended_at is not None:
            entry["total_duration_seconds"] += _duration_seconds(started_at, ended_at)
        latest = ended_at or started_at
        if entry["last_activity"] is None or latest > entry["last_activity"]:
            entry["last_activity"] = latest

    return sorted(projects.values(), key=lambda p: p["name"])


def recent_decisions(limit: int = 20) -> list[dict]:
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT decisions.decision, decisions.reasoning,
                   decisions.rejected_alternative, decisions.created_at, projects.name
            FROM decisions
            JOIN sessions ON sessions.id = decisions.session_id
            JOIN projects ON projects.id = sessions.project_id
            ORDER BY decisions.created_at DESC, decisions.id DESC
            LIMIT ?
            """,
            (limit,),
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


def skill_usage_counts() -> list[dict]:
    """Every current skill with its all-time fetch count (0 if never
    fetched), so the dashboard can show a full usage picture, not just the
    skills that happen to have activity."""
    with db_connection() as conn:
        rows = conn.execute(
            "SELECT skill_name, COUNT(*) FROM skill_usage "
            "WHERE action = 'fetched' GROUP BY skill_name"
        ).fetchall()
    counts = dict(rows)

    return [
        {
            "name": skill["name"],
            "title": skill["title"],
            "category": skill["category"],
            "path": skill["path"],
            "fetch_count": counts.get(skill["name"], 0),
        }
        for skill in skills_store.load_all_skills()
    ]


def _content_tokens_in_range(start: str, end: str) -> dict:
    """Actual content served: every 'listed' row's metadata size plus every
    'fetched' row's body size (NULL sizes -- pre-instrumentation history,
    or a not-found fetch with no body -- are excluded by SUM, not treated
    as zero).

    tokens_est is derived from the summed chars (estimate_tokens once on
    the total), not by summing each row's already-stored tokens_est --
    summing individually floor-divided per-row estimates can drift a few
    tokens from flooring the total once, and the baseline side (see
    library_baseline) is computed the same single-floor way. Both sides
    of the saving comparison must use the identical rule or the "saving"
    number stops being exactly defensible.
    """
    with db_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(chars), 0) "
            "FROM skill_usage WHERE created_at BETWEEN ? AND ?",
            (start, end),
        ).fetchone()
    chars = row[0]
    return {"chars": chars, "tokens_est": token_metrics.estimate_tokens(chars)}


def _content_tokens_cumulative() -> dict:
    with db_connection() as conn:
        row = conn.execute("SELECT COALESCE(SUM(chars), 0) FROM skill_usage").fetchone()
    chars = row[0]
    return {"chars": chars, "tokens_est": token_metrics.estimate_tokens(chars)}


def library_baseline() -> dict | None:
    """Most recent library snapshot: the baseline "as if the whole library
    had been loaded into context up front." None if the server has never
    started (no snapshot taken yet)."""
    with db_connection() as conn:
        row = conn.execute(
            "SELECT total_skills, total_chars, total_tokens_est, created_at "
            "FROM library_snapshots ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    return {
        "total_skills": row[0],
        "chars": row[1],
        "tokens_est": row[2],
        "snapshot_at": row[3],
    }


def compute_token_report(period: str | None = None, now: datetime | None = None) -> dict:
    """Actual content served vs. the whole-library baseline, for a window
    (weekly/monthly, matching Session 3's rolling windows) or cumulative
    (period=None, no date filter at all).

    Labeled "context content tokens (estimated)" throughout -- this is the
    size of content this server served, not client-billed API tokens,
    which aren't visible from here. See docs/decision-log.md.
    """
    if period is None:
        range_start, range_end = None, None
        actual = _content_tokens_cumulative()
    else:
        range_start, range_end = period_bounds(period, now)
        actual = _content_tokens_in_range(range_start, range_end)

    baseline = library_baseline()
    if baseline is None:
        baseline_tokens_est = None
        saving_tokens_est = None
        saving_pct = None
    else:
        baseline_tokens_est = baseline["tokens_est"]
        saving_tokens_est = baseline_tokens_est - actual["tokens_est"]
        saving_pct = (
            round(saving_tokens_est / baseline_tokens_est * 100, 1)
            if baseline_tokens_est
            else None
        )

    return {
        "period": period,
        "range_start": range_start,
        "range_end": range_end,
        "actual_chars": actual["chars"],
        "actual_tokens_est": actual["tokens_est"],
        "baseline_chars": baseline["chars"] if baseline else None,
        "baseline_tokens_est": baseline_tokens_est,
        "baseline_snapshot_at": baseline["snapshot_at"] if baseline else None,
        "saving_tokens_est": saving_tokens_est,
        "saving_pct": saving_pct,
        "label": "context content tokens (estimated), not client-billed API tokens",
    }
