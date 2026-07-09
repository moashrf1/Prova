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


def seed_skill_usage(db_path, skill_name, action, created_at, chars=None, tokens_est=None):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO skill_usage (skill_name, action, created_at, chars, tokens_est) "
            "VALUES (?, ?, ?, ?, ?)",
            (skill_name, action, created_at, chars, tokens_est),
        )


def seed_library_snapshot(db_path, total_skills, total_chars, total_tokens_est, created_at):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO library_snapshots (total_skills, total_chars, total_tokens_est, created_at) "
            "VALUES (?, ?, ?, ?)",
            (total_skills, total_chars, total_tokens_est, created_at),
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


def test_project_rollups_aggregates_sessions_and_duration(isolated_analytics):
    db_path = isolated_analytics
    now = datetime.utcnow()

    seed_session(db_path, "proj-a", ts(now, 5), ts(now, 5, hours=1))
    seed_session(db_path, "proj-a", ts(now, 1), ts(now, 1, hours=2))
    seed_session(db_path, "proj-b", ts(now, 3), None)  # open

    rollups = {r["name"]: r for r in analytics_store.project_rollups()}

    assert rollups["proj-a"]["session_count"] == 2
    assert rollups["proj-a"]["total_duration_seconds"] == 10800.0  # 1h + 2h
    assert rollups["proj-a"]["last_activity"] == ts(now, 1, hours=2)

    assert rollups["proj-b"]["session_count"] == 1
    assert rollups["proj-b"]["total_duration_seconds"] == 0.0
    assert rollups["proj-b"]["last_activity"] == ts(now, 3)


def test_project_rollups_includes_project_with_no_sessions(isolated_analytics):
    with sqlite3.connect(analytics_store.DB_PATH) as conn:
        conn.execute("INSERT INTO projects (name) VALUES ('untouched-proj')")
        conn.commit()

    rollups = {r["name"]: r for r in analytics_store.project_rollups()}

    assert rollups["untouched-proj"]["session_count"] == 0
    assert rollups["untouched-proj"]["total_duration_seconds"] == 0.0
    assert rollups["untouched-proj"]["last_activity"] is None


def test_recent_decisions_ordered_newest_first_and_respects_limit(isolated_analytics):
    db_path = isolated_analytics
    now = datetime.utcnow()

    session_id = seed_session(db_path, "proj", ts(now, 5), ts(now, 5, hours=1))
    seed_decision(db_path, session_id, "older decision", "reasoning A", ts(now, 3))
    seed_decision(db_path, session_id, "newer decision", "reasoning B", ts(now, 1))

    decisions = analytics_store.recent_decisions(limit=1)

    assert len(decisions) == 1
    assert decisions[0]["decision"] == "newer decision"


def test_skill_usage_counts_includes_zero_fetch_skills(isolated_analytics):
    db_path = isolated_analytics
    now = datetime.utcnow()

    seed_skill_usage(db_path, "skill-a", "fetched", ts(now, 1))
    seed_skill_usage(db_path, "skill-a", "fetched", ts(now, 2))

    counts = {s["name"]: s["fetch_count"] for s in analytics_store.skill_usage_counts()}

    assert counts["skill-a"] == 2
    assert counts["skill-b"] == 0
    assert counts["skill-c"] == 0


def test_skill_usage_counts_excludes_nonexistent_skill_names(isolated_analytics):
    db_path = isolated_analytics
    now = datetime.utcnow()

    seed_skill_usage(db_path, "typo-name", "fetched", ts(now, 1))

    names = {s["name"] for s in analytics_store.skill_usage_counts()}

    assert "typo-name" not in names
    assert names == {"skill-a", "skill-b", "skill-c"}


def test_library_baseline_returns_none_without_a_snapshot(isolated_analytics):
    assert analytics_store.library_baseline() is None


def test_library_baseline_returns_most_recent_snapshot(isolated_analytics):
    db_path = isolated_analytics
    now = datetime.utcnow()

    seed_library_snapshot(db_path, 3, 3000, 750, ts(now, 2))
    seed_library_snapshot(db_path, 4, 4000, 1000, ts(now, 1))

    baseline = analytics_store.library_baseline()

    assert baseline["total_skills"] == 4
    assert baseline["chars"] == 4000
    assert baseline["tokens_est"] == 1000


def test_token_report_weekly_window_excludes_older_usage(isolated_analytics):
    db_path = isolated_analytics
    now = datetime.utcnow()

    seed_library_snapshot(db_path, 3, 4000, 1000, ts(now, 30))
    seed_skill_usage(db_path, "skill-a", "listed", ts(now, 1), chars=100, tokens_est=25)
    seed_skill_usage(db_path, "skill-a", "fetched", ts(now, 1), chars=300, tokens_est=75)
    seed_skill_usage(db_path, "skill-b", "fetched", ts(now, 20), chars=500, tokens_est=125)

    report = analytics_store.compute_token_report("weekly", now=now)

    assert report["actual_chars"] == 400  # only the two rows within 7 days
    assert report["actual_tokens_est"] == 100
    assert report["baseline_chars"] == 4000
    assert report["baseline_tokens_est"] == 1000
    assert report["saving_tokens_est"] == 900
    assert report["saving_pct"] == 90.0


def test_token_report_monthly_window_includes_wider_range(isolated_analytics):
    db_path = isolated_analytics
    now = datetime.utcnow()

    seed_library_snapshot(db_path, 3, 4000, 1000, ts(now, 30))
    seed_skill_usage(db_path, "skill-a", "fetched", ts(now, 1), chars=300, tokens_est=75)
    seed_skill_usage(db_path, "skill-b", "fetched", ts(now, 20), chars=500, tokens_est=125)

    report = analytics_store.compute_token_report("monthly", now=now)

    assert report["actual_chars"] == 800


def test_token_report_cumulative_ignores_date_window(isolated_analytics):
    db_path = isolated_analytics
    now = datetime.utcnow()

    seed_library_snapshot(db_path, 3, 4000, 1000, ts(now, 30))
    seed_skill_usage(db_path, "skill-a", "fetched", ts(now, 90), chars=300, tokens_est=75)
    seed_skill_usage(db_path, "skill-b", "fetched", ts(now, 200), chars=500, tokens_est=125)

    report = analytics_store.compute_token_report(None, now=now)

    assert report["period"] is None
    assert report["range_start"] is None
    assert report["actual_chars"] == 800  # both rows counted, regardless of age


def test_token_report_derives_tokens_est_from_summed_chars_not_summed_estimates(isolated_analytics):
    """Regression test for the rounding-consistency bug found during Session
    6: summing individually floor-divided per-row tokens_est can drift from
    flooring the summed chars once. Seeded so the two methods would disagree
    if the bug were reintroduced (three rows of 7 chars/1 token each: sum of
    per-row floors = 3, but floor(21/4) = 5)."""
    db_path = isolated_analytics
    now = datetime.utcnow()

    seed_library_snapshot(db_path, 1, 1000, 250, ts(now, 30))
    for _ in range(3):
        seed_skill_usage(db_path, "skill-a", "fetched", ts(now, 1), chars=7, tokens_est=1)

    report = analytics_store.compute_token_report("weekly", now=now)

    assert report["actual_chars"] == 21
    assert report["actual_tokens_est"] == 5  # floor(21 / 4), not 3 (sum of per-row floors)


def test_token_report_no_snapshot_returns_none_baseline(isolated_analytics):
    db_path = isolated_analytics
    now = datetime.utcnow()
    seed_skill_usage(db_path, "skill-a", "fetched", ts(now, 1), chars=100, tokens_est=25)

    report = analytics_store.compute_token_report("weekly", now=now)

    assert report["baseline_tokens_est"] is None
    assert report["saving_tokens_est"] is None
    assert report["saving_pct"] is None
    assert report["actual_chars"] == 100


def test_recap_includes_token_saving_block_matching_token_report(isolated_analytics):
    db_path = isolated_analytics
    now = datetime.utcnow()

    seed_library_snapshot(db_path, 3, 4000, 1000, ts(now, 30))
    seed_skill_usage(db_path, "skill-a", "fetched", ts(now, 1), chars=300, tokens_est=75)

    recap = analytics_store.compute_recap("weekly", now=now)
    report = analytics_store.compute_token_report("weekly", now=now)

    assert recap["token_saving"]["actual_tokens_est"] == report["actual_tokens_est"]
    assert recap["token_saving"]["baseline_tokens_est"] == report["baseline_tokens_est"]
    assert recap["token_saving"]["saving_tokens_est"] == report["saving_tokens_est"]
    assert recap["token_saving"]["saving_pct"] == report["saving_pct"]
