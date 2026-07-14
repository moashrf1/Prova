import sqlite3
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import analytics_store
import skills_store
import work_store
from web.app import app

TIMESTAMP_FORMAT = analytics_store.TIMESTAMP_FORMAT


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "data" / "enablement.db"
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    monkeypatch.setattr(skills_store, "DB_PATH", db_path)
    monkeypatch.setattr(skills_store, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(work_store, "DB_PATH", db_path)
    monkeypatch.setattr(analytics_store, "DB_PATH", db_path)

    (skills_dir / "a.md").write_text(
        "---\nname: skill-a\ntitle: A\ndescription: d\ncategory: technical\n"
        "path: null\ntags: [t]\n---\n# Body\n"
    )

    skills_store.init_db()
    work_store.init_db()

    return TestClient(app)


def test_recap_endpoint_matches_analytics_store(client, tmp_path):
    now = datetime.utcnow()
    ts = now.strftime(TIMESTAMP_FORMAT)
    ts_end = (now).strftime(TIMESTAMP_FORMAT)

    with sqlite3.connect(work_store.DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("INSERT INTO projects (name) VALUES ('demo')")
        pid = conn.execute("SELECT id FROM projects WHERE name='demo'").fetchone()[0]
        conn.execute(
            "INSERT INTO sessions (project_id, started_at, ended_at) VALUES (?, ?, ?)",
            (pid, ts, ts_end),
        )
        conn.commit()

    response = client.get("/api/recap", params={"period": "weekly"})

    assert response.status_code == 200
    body = response.json()
    expected = analytics_store.compute_recap("weekly")
    assert body["session_count"] == expected["session_count"] == 1
    assert body["projects_touched"] == ["demo"]


def test_recap_endpoint_rejects_bad_period(client):
    response = client.get("/api/recap", params={"period": "yearly"})
    assert response.status_code == 400


def test_recap_endpoint_returns_503_when_db_missing(tmp_path, monkeypatch):
    missing_db = tmp_path / "does-not-exist" / "enablement.db"
    monkeypatch.setattr(analytics_store, "DB_PATH", missing_db)
    client = TestClient(app)

    response = client.get("/api/recap", params={"period": "weekly"})

    assert response.status_code == 503


def test_learning_stats_endpoint(client):
    response = client.get("/api/learning-stats", params={"path": "product-manager"})

    assert response.status_code == 200
    body = response.json()
    assert body["path"] == "product-manager"
    assert "path_skill_total" in body


def test_learning_stats_endpoint_without_path(client):
    response = client.get("/api/learning-stats")

    assert response.status_code == 200
    assert "path" not in response.json()


def test_projects_endpoint(client):
    with sqlite3.connect(work_store.DB_PATH) as conn:
        conn.execute("INSERT INTO projects (name) VALUES ('proj-x')")
        conn.commit()

    response = client.get("/api/projects")

    assert response.status_code == 200
    names = {p["name"] for p in response.json()}
    assert "proj-x" in names


def test_decisions_endpoint_respects_limit(client):
    with sqlite3.connect(work_store.DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("INSERT INTO projects (name) VALUES ('proj-y')")
        pid = conn.execute("SELECT id FROM projects WHERE name='proj-y'").fetchone()[0]
        conn.execute(
            "INSERT INTO sessions (project_id, started_at, ended_at) VALUES (?, datetime('now'), datetime('now'))",
            (pid,),
        )
        sid = conn.execute("SELECT id FROM sessions").fetchone()[0]
        conn.execute(
            "INSERT INTO decisions (session_id, decision, reasoning) VALUES (?, 'd1', 'r1')",
            (sid,),
        )
        conn.execute(
            "INSERT INTO decisions (session_id, decision, reasoning) VALUES (?, 'd2', 'r2')",
            (sid,),
        )
        conn.commit()

    response = client.get("/api/decisions", params={"limit": 1})

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_decisions_endpoint_rejects_bad_limit(client):
    response = client.get("/api/decisions", params={"limit": 0})
    assert response.status_code == 400


def test_skills_endpoint_includes_seed_skill(client):
    response = client.get("/api/skills")

    assert response.status_code == 200
    names = {s["name"] for s in response.json()}
    assert "skill-a" in names


def test_skill_engagement_endpoint_matches_analytics_store(client):
    response = client.get("/api/skill-engagement")

    assert response.status_code == 200
    body = {s["name"]: s for s in response.json()}
    expected = {s["name"]: s for s in analytics_store.skill_engagement_overview()}
    assert body == expected
    assert "skill-a" in body
    assert set(body["skill-a"].keys()) == {"name", "title", "category", "path", "fetched", "referenced_only"}


def test_token_report_endpoint_matches_analytics_store(client):
    skills_store.record_library_snapshot()
    skill = skills_store.load_all_skills()[0]
    chars, tokens_est = skills_store.measure_listing(skill)
    skills_store.log_usage(skill["name"], "listed", chars, tokens_est)

    response = client.get("/api/token-report", params={"period": "weekly"})

    assert response.status_code == 200
    body = response.json()
    expected = analytics_store.compute_token_report("weekly")
    assert body["actual_chars"] == expected["actual_chars"] == chars
    assert body["baseline_tokens_est"] == expected["baseline_tokens_est"]
    assert body["saving_tokens_est"] == expected["saving_tokens_est"]


def test_token_report_endpoint_cumulative_when_period_omitted(client):
    skills_store.record_library_snapshot()

    response = client.get("/api/token-report")

    assert response.status_code == 200
    assert response.json()["period"] is None


def test_token_report_endpoint_rejects_bad_period(client):
    response = client.get("/api/token-report", params={"period": "yearly"})
    assert response.status_code == 400


def test_token_report_endpoint_handles_no_snapshot_yet(client):
    response = client.get("/api/token-report", params={"period": "weekly"})

    assert response.status_code == 200
    assert response.json()["baseline_tokens_est"] is None


def test_tech_stack_endpoint_matches_analytics_store(client):
    with sqlite3.connect(work_store.DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("INSERT INTO projects (name) VALUES ('proj-z')")
        pid = conn.execute("SELECT id FROM projects WHERE name='proj-z'").fetchone()[0]
        conn.execute(
            "INSERT INTO sessions (project_id, started_at, ended_at) VALUES "
            "(?, datetime('now'), datetime('now'))",
            (pid,),
        )
        sid = conn.execute("SELECT id FROM sessions").fetchone()[0]
        conn.execute(
            "INSERT INTO worklog (session_id, tasks) VALUES (?, 'Wrote a python script')",
            (sid,),
        )
        conn.commit()

    response = client.get("/api/tech-stack")

    assert response.status_code == 200
    body = response.json()
    assert body == analytics_store.tech_stack_usage()
    assert {u["name"] for u in body} == {"Python"}
