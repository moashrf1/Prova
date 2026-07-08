import sqlite3

import pytest

import work_store


@pytest.fixture
def isolated_work_store(tmp_path, monkeypatch):
    db_path = tmp_path / "data" / "enablement.db"
    monkeypatch.setattr(work_store, "DB_PATH", db_path)
    work_store.init_db()
    return db_path


def test_get_or_create_project_returns_same_id_on_repeat(isolated_work_store):
    first = work_store.get_or_create_project("demo-project")
    second = work_store.get_or_create_project("demo-project")

    assert first == second
    with sqlite3.connect(isolated_work_store) as conn:
        count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    assert count == 1


def test_get_or_create_open_session_reuses_while_open(isolated_work_store):
    project_id = work_store.get_or_create_project("demo-project")

    first = work_store.get_or_create_open_session(project_id)
    second = work_store.get_or_create_open_session(project_id)
    assert first == second

    work_store.close_session(first)
    third = work_store.get_or_create_open_session(project_id)
    assert third != first


def test_foreign_key_enforcement_rejects_bad_project_id(isolated_work_store):
    with work_store.db_connection() as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO sessions (project_id) VALUES (?)", (99999,)
            )


def test_foreign_key_enforcement_rejects_bad_session_id(isolated_work_store):
    with work_store.db_connection() as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO worklog (session_id, tasks) VALUES (?, ?)",
                (99999, "some task"),
            )


def test_log_work_writes_linked_worklog_row(isolated_work_store):
    result = work_store.log_work(
        "demo-project", tasks="did the thing", learnings="learned a thing"
    )

    with sqlite3.connect(isolated_work_store) as conn:
        row = conn.execute(
            "SELECT session_id, tasks, learnings FROM worklog WHERE id = ?",
            (result["worklog_id"],),
        ).fetchone()
    assert row == (result["session_id"], "did the thing", "learned a thing")

    with sqlite3.connect(isolated_work_store) as conn:
        ended_at = conn.execute(
            "SELECT ended_at FROM sessions WHERE id = ?", (result["session_id"],)
        ).fetchone()[0]
    assert ended_at is not None


def test_log_work_twice_same_project_reuses_project_two_worklog_rows(
    isolated_work_store,
):
    first = work_store.log_work("demo-project", tasks="task one")
    second = work_store.log_work("demo-project", tasks="task two")

    assert first["project_id"] == second["project_id"]
    assert first["session_id"] != second["session_id"]

    with sqlite3.connect(isolated_work_store) as conn:
        project_count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        worklog_count = conn.execute("SELECT COUNT(*) FROM worklog").fetchone()[0]
    assert project_count == 1
    assert worklog_count == 2


def test_log_decision_with_rejected_alternative(isolated_work_store):
    result = work_store.log_decision(
        "demo-project",
        decision="Use SQLite",
        reasoning="Single-user, no ops overhead",
        rejected_alternative="Postgres -- overkill",
    )

    with sqlite3.connect(isolated_work_store) as conn:
        row = conn.execute(
            "SELECT decision, reasoning, rejected_alternative FROM decisions WHERE id = ?",
            (result["decision_id"],),
        ).fetchone()
    assert row == ("Use SQLite", "Single-user, no ops overhead", "Postgres -- overkill")


def test_log_decision_without_rejected_alternative(isolated_work_store):
    result = work_store.log_decision(
        "demo-project",
        decision="Log usage on every fetch",
        reasoning="Needed for analytics later",
    )

    with sqlite3.connect(isolated_work_store) as conn:
        rejected = conn.execute(
            "SELECT rejected_alternative FROM decisions WHERE id = ?",
            (result["decision_id"],),
        ).fetchone()[0]
    assert rejected is None


def test_decisions_share_session_with_following_log_work(isolated_work_store):
    d1 = work_store.log_decision("demo-project", "Decision A", "Reason A")
    d2 = work_store.log_decision("demo-project", "Decision B", "Reason B")
    work = work_store.log_work("demo-project", tasks="wrapped up")

    assert d1["session_id"] == d2["session_id"] == work["session_id"]

    with sqlite3.connect(isolated_work_store) as conn:
        decision_count = conn.execute(
            "SELECT COUNT(*) FROM decisions WHERE session_id = ?",
            (work["session_id"],),
        ).fetchone()[0]
        worklog_count = conn.execute(
            "SELECT COUNT(*) FROM worklog WHERE session_id = ?",
            (work["session_id"],),
        ).fetchone()[0]
    assert decision_count == 2
    assert worklog_count == 1
