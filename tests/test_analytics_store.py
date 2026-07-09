import sqlite3
from datetime import datetime, timedelta

import pytest

import analytics_store
import skills_store
import work_store

TIMESTAMP_FORMAT = analytics_store.TIMESTAMP_FORMAT


def write_skill(skills_dir, filename, name, path):
    content = (
        "---\n"
        f"name: {name}\n"
        f"title: {name}\n"
        "description: A test skill.\n"
        "category: technical\n"
        f"path: {path if path is not None else 'null'}\n"
        "tags: [test]\n"
        "---\n"
        "# Body\n\nContent.\n"
    )
    (skills_dir / filename).write_text(content)


@pytest.fixture
def isolated_analytics(tmp_path, monkeypatch):
    db_path = tmp_path / "data" / "enablement.db"
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    monkeypatch.setattr(skills_store, "DB_PATH", db_path)
    monkeypatch.setattr(skills_store, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(work_store, "DB_PATH", db_path)
    monkeypatch.setattr(analytics_store, "DB_PATH", db_path)

    write_skill(skills_dir, "a.md", "skill-a", "test-path")
    write_skill(skills_dir, "b.md", "skill-b", "test-path")
    write_skill(skills_dir, "c.md", "skill-c", None)

    skills_store.init_db()
    work_store.init_db()

    return db_path


def ts(now, days_ago, hours=0):
    return (now - timedelta(days=days_ago, hours=-hours)).strftime(TIMESTAMP_FORMAT)


def seed_session(db_path, project_name, started_at, ended_at=None):
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("INSERT OR IGNORE INTO projects (name) VALUES (?)", (project_name,))
        project_id = conn.execute(
            "SELECT id FROM projects WHERE name = ?", (project_name,)
        ).fetchone()[0]
        cursor = conn.execute(
            "INSERT INTO sessions (project_id, started_at, ended_at) VALUES (?, ?, ?)",
            (project_id, started_at, ended_at),
        )
        return cursor.lastrowid


def seed_worklog(db_path, session_id, tasks, created_at, learnings=None):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO worklog (session_id, tasks, learnings, created_at) VALUES (?, ?, ?, ?)",
            (session_id, tasks, learnings, created_at),
        )


def seed_decision(db_path, session_id, decision, reasoning, created_at, rejected=None):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO decisions (session_id, decision, reasoning, rejected_alternative, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, decision, reasoning, rejected, created_at),
        )


def seed_skill_usage(db_path, skill_name, action, created_at):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO skill_usage (skill_name, action, created_at) VALUES (?, ?, ?)",
            (skill_name, action, created_at),
        )


def test_weekly_recap_excludes_older_sessions(isolated_analytics):
    db_path = isolated_analytics
    now = datetime.utcnow()

    recent = seed_session(db_path, "proj", ts(now, 3), ts(now, 3, hours=2))
    seed_session(db_path, "proj", ts(now, 20), ts(now, 20, hours=1))

    recap = analytics_store.compute_recap("weekly", now=now)

    assert recap["session_count"] == 1
    assert recap["total_duration_seconds"] == 7200.0


def test_monthly_recap_includes_wider_range(isolated_analytics):
    db_path = isolated_analytics
    now = datetime.utcnow()

    seed_session(db_path, "proj", ts(now, 3), ts(now, 3, hours=2))
    seed_session(db_path, "proj", ts(now, 20), ts(now, 20, hours=1))
    seed_session(db_path, "proj", ts(now, 45), ts(now, 45, hours=1))

    recap = analytics_store.compute_recap("monthly", now=now)

    assert recap["session_count"] == 2
    assert recap["total_duration_seconds"] == 10800.0


def test_recap_excludes_open_sessions_from_duration_but_counts_them(isolated_analytics):
    db_path = isolated_analytics
    now = datetime.utcnow()

    seed_session(db_path, "proj", ts(now, 1), ts(now, 1, hours=1))
    seed_session(db_path, "proj", ts(now, 1), None)  # still open

    recap = analytics_store.compute_recap("weekly", now=now)

    assert recap["session_count"] == 2
    assert recap["open_session_count"] == 1
    assert recap["total_duration_seconds"] == 3600.0


def test_recap_includes_worklog_and_decisions_for_period(isolated_analytics):
    db_path = isolated_analytics
    now = datetime.utcnow()

    session_id = seed_session(db_path, "proj", ts(now, 1), ts(now, 1, hours=1))
    seed_worklog(db_path, session_id, "did work", ts(now, 1, hours=1), learnings="learned")
    seed_decision(db_path, session_id, "chose X", "because Y", ts(now, 1), rejected="Z")

    recap = analytics_store.compute_recap("weekly", now=now)

    assert recap["worklog_count"] == 1
    assert recap["worklog_entries"][0]["tasks"] == "did work"
    assert recap["decision_count"] == 1
    assert recap["decisions"][0]["rejected_alternative"] == "Z"


def test_recap_skills_fetched_excludes_nonexistent_names(isolated_analytics):
    db_path = isolated_analytics
    now = datetime.utcnow()

    seed_skill_usage(db_path, "skill-a", "fetched", ts(now, 1))
    seed_skill_usage(db_path, "typo-name", "fetched", ts(now, 1))

    recap = analytics_store.compute_recap("weekly", now=now)

    assert recap["skills_fetched"] == ["skill-a"]


def test_learning_stats_path_progress_fetched_vs_total(isolated_analytics):
    db_path = isolated_analytics
    now = datetime.utcnow()

    seed_skill_usage(db_path, "skill-a", "fetched", ts(now, 1))

    stats = analytics_store.compute_learning_stats("test-path")

    assert stats["path_skill_total"] == 2
    assert stats["path_skill_fetched_count"] == 1
    assert stats["path_skills_fetched"] == ["skill-a"]
    assert stats["path_skills_remaining"] == ["skill-b"]


def test_learning_stats_cumulative_ignores_date_window(isolated_analytics):
    db_path = isolated_analytics
    now = datetime.utcnow()

    old_session = seed_session(db_path, "old-proj", ts(now, 90), ts(now, 90, hours=1))
    seed_decision(db_path, old_session, "old decision", "old reasoning", ts(now, 90))
    seed_skill_usage(db_path, "skill-c", "fetched", ts(now, 90))

    stats = analytics_store.compute_learning_stats()

    assert stats["total_sessions"] == 1
    assert stats["total_decisions"] == 1
    assert stats["total_distinct_skills_fetched"] == 1
    assert "path" not in stats


def test_learning_stats_without_path_omits_path_keys(isolated_analytics):
    stats = analytics_store.compute_learning_stats(None)

    assert stats == {
        "total_sessions": 0,
        "total_decisions": 0,
        "total_distinct_skills_fetched": 0,
    }
