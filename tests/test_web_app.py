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
