"""Structural tech-stack detection: scans a local git repository's own
commit history for source files, by extension.

This is a different signal from tech_stack.py (which infers language
mentions from worklog prose) and from analytics_store.py (which is
read-only). A worklog entry that never happens to spell out "Python" or
"JavaScript" still leaves a precise trail in its own repository -- the
files it actually contains. This module reads that trail directly instead
of depending on how someone happened to word a summary.

The ai-enablement-system's own database has no notion of "where a
project's code lives" -- projects are just names. So the caller supplies
a repo_path explicitly each time; this can only see repositories on the
machine actually running this MCP server, which is the point: it runs
wherever you (the worker) actually are, scanning the repo that's actually
in front of you.
"""

import sqlite3
import subprocess
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "enablement.db"

# Same language names as tech_stack.py's vocabulary, keyed by file extension
# instead of by regex pattern, so the two signals stay comparable on a chart.
EXTENSION_LANGUAGE: dict[str, str] = {
    ".py": "Python",
    ".sql": "SQL",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".cs": "C#",
    ".cpp": "C++",
    ".cc": "C++",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".html": "HTML",
    ".css": "CSS",
    ".sh": "Bash",
    ".ps1": "PowerShell",
}


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
            CREATE TABLE IF NOT EXISTS repo_tech_scans (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id  INTEGER NOT NULL REFERENCES projects(id),
                language    TEXT NOT NULL,
                file_count  INTEGER NOT NULL,
                scanned_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watched_projects (
                project_id      INTEGER PRIMARY KEY REFERENCES projects(id),
                repo_path       TEXT NOT NULL,
                last_scanned_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )


def scan_git_repo(repo_path: str) -> dict[str, int]:
    """Every distinct filename that has ever existed in repo_path's commit
    history (reachable from HEAD), counted once each by extension -- "how
    many files of this language exist across the project's history," not
    "how many commits touched a file of this language."

    Raises ValueError if repo_path isn't a git repository (or has no
    commits yet) rather than surfacing a raw subprocess error.
    """
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "log", "--name-only", "--pretty=format:"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise ValueError(
            f"'{repo_path}' doesn't look like a git repository with any commits."
        ) from exc

    filenames = {line.strip() for line in result.stdout.splitlines() if line.strip()}

    counts: dict[str, int] = {}
    for filename in filenames:
        language = EXTENSION_LANGUAGE.get(Path(filename).suffix.lower())
        if language is not None:
            counts[language] = counts.get(language, 0) + 1
    return counts


def _get_or_create_project_id(conn: sqlite3.Connection, project_name: str) -> int:
    conn.execute("INSERT OR IGNORE INTO projects (name) VALUES (?)", (project_name,))
    return conn.execute(
        "SELECT id FROM projects WHERE name = ?", (project_name,)
    ).fetchone()[0]


def record_repo_scan(project_name: str, repo_path: str) -> list[dict]:
    """Scan repo_path and replace any previous scan recorded for this
    project -- a rescan reflects the repo's current history, it doesn't
    accumulate a duplicate row set on top of the last scan.

    Also registers (project_id, repo_path) in watched_projects, so a
    single manual scan is all that's needed to make a project eligible
    for scan_all_watched_projects() from then on -- there's no separate
    "register this project" step to remember."""
    counts = scan_git_repo(repo_path)

    with db_connection() as conn:
        project_id = _get_or_create_project_id(conn, project_name)
        conn.execute("DELETE FROM repo_tech_scans WHERE project_id = ?", (project_id,))
        for language, file_count in counts.items():
            conn.execute(
                "INSERT INTO repo_tech_scans (project_id, language, file_count) "
                "VALUES (?, ?, ?)",
                (project_id, language, file_count),
            )
        conn.execute(
            "INSERT INTO watched_projects (project_id, repo_path, last_scanned_at) "
            "VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(project_id) DO UPDATE SET "
            "repo_path = excluded.repo_path, last_scanned_at = excluded.last_scanned_at",
            (project_id, repo_path),
        )

    return [
        {"name": language, "file_count": count}
        for language, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def scan_all_watched_projects() -> list[dict]:
    """Rescan every project previously registered via record_repo_scan,
    without needing to name each repo_path again.

    A path that's moved or been deleted since its last scan is reported
    as an error for that one project rather than aborting the whole
    batch -- one stale project shouldn't block getting fresh data for
    everything else being watched."""
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT projects.name, watched_projects.repo_path
            FROM watched_projects
            JOIN projects ON projects.id = watched_projects.project_id
            """
        ).fetchall()

    results = []
    for project_name, repo_path in rows:
        try:
            languages = record_repo_scan(project_name, repo_path)
            results.append({"project": project_name, "repo_path": repo_path, "languages": languages})
        except ValueError as exc:
            results.append({"project": project_name, "repo_path": repo_path, "error": str(exc)})

    return results
