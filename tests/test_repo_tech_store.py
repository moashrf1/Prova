import sqlite3
import subprocess

import pytest

import repo_tech_store


def make_git_repo(path, files: dict[str, str]):
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    for name, content in files.items():
        (path / name).write_text(content)
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=path, check=True)


@pytest.fixture
def isolated_repo_tech_store(tmp_path, monkeypatch):
    db_path = tmp_path / "data" / "enablement.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(repo_tech_store, "DB_PATH", db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            "CREATE TABLE projects (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "name TEXT NOT NULL UNIQUE, description TEXT, status TEXT NOT NULL DEFAULT 'active', "
            "created_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )

    repo_tech_store.init_db()
    return db_path


def test_scan_git_repo_counts_files_by_extension(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    make_git_repo(
        repo,
        {
            "server.py": "print('hi')",
            "utils.py": "pass",
            "index.html": "<html></html>",
            "style.css": "body {}",
            "README.md": "# readme",  # unrecognized extension, should be ignored
        },
    )

    counts = repo_tech_store.scan_git_repo(str(repo))

    assert counts == {"Python": 2, "HTML": 1, "CSS": 1}


def test_scan_git_repo_counts_distinct_filenames_once_across_history(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    make_git_repo(repo, {"main.py": "v1"})
    (repo / "main.py").write_text("v2")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "second commit, same file"], cwd=repo, check=True)

    counts = repo_tech_store.scan_git_repo(str(repo))

    assert counts == {"Python": 1}  # edited twice, still one file


def test_scan_git_repo_raises_on_non_git_directory(tmp_path):
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()

    with pytest.raises(ValueError):
        repo_tech_store.scan_git_repo(str(not_a_repo))


def test_record_repo_scan_stores_and_returns_sorted_counts(tmp_path, isolated_repo_tech_store):
    repo = tmp_path / "repo"
    repo.mkdir()
    make_git_repo(repo, {"a.py": "1", "b.py": "2", "c.sql": "SELECT 1"})

    result = repo_tech_store.record_repo_scan("demo-project", str(repo))

    assert result == [{"name": "Python", "file_count": 2}, {"name": "SQL", "file_count": 1}]

    with sqlite3.connect(isolated_repo_tech_store) as conn:
        rows = conn.execute(
            "SELECT language, file_count FROM repo_tech_scans WHERE project_id = "
            "(SELECT id FROM projects WHERE name = 'demo-project')"
        ).fetchall()
    assert set(rows) == {("Python", 2), ("SQL", 1)}


def test_record_repo_scan_rescan_replaces_previous_rows(tmp_path, isolated_repo_tech_store):
    repo = tmp_path / "repo"
    repo.mkdir()
    make_git_repo(repo, {"a.py": "1"})

    repo_tech_store.record_repo_scan("demo-project", str(repo))

    (repo / "b.js").write_text("console.log(1)")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add a js file"], cwd=repo, check=True)

    result = repo_tech_store.record_repo_scan("demo-project", str(repo))

    assert result == [{"name": "JavaScript", "file_count": 1}, {"name": "Python", "file_count": 1}]

    with sqlite3.connect(isolated_repo_tech_store) as conn:
        row_count = conn.execute("SELECT COUNT(*) FROM repo_tech_scans").fetchone()[0]
    assert row_count == 2  # not 4 -- the first scan's rows were replaced, not kept alongside


def test_record_repo_scan_auto_creates_project(tmp_path, isolated_repo_tech_store):
    repo = tmp_path / "repo"
    repo.mkdir()
    make_git_repo(repo, {"a.py": "1"})

    repo_tech_store.record_repo_scan("brand-new-project", str(repo))

    with sqlite3.connect(isolated_repo_tech_store) as conn:
        names = {r[0] for r in conn.execute("SELECT name FROM projects").fetchall()}
    assert "brand-new-project" in names


def test_record_repo_scan_registers_watched_project(tmp_path, isolated_repo_tech_store):
    repo = tmp_path / "repo"
    repo.mkdir()
    make_git_repo(repo, {"a.py": "1"})

    repo_tech_store.record_repo_scan("demo-project", str(repo))

    with sqlite3.connect(isolated_repo_tech_store) as conn:
        row = conn.execute(
            "SELECT repo_path FROM watched_projects WHERE project_id = "
            "(SELECT id FROM projects WHERE name = 'demo-project')"
        ).fetchone()
    assert row == (str(repo),)


def test_record_repo_scan_rescan_updates_watched_project_path(tmp_path, isolated_repo_tech_store):
    repo_a = tmp_path / "repo_a"
    repo_a.mkdir()
    make_git_repo(repo_a, {"a.py": "1"})
    repo_tech_store.record_repo_scan("demo-project", str(repo_a))

    repo_b = tmp_path / "repo_b"
    repo_b.mkdir()
    make_git_repo(repo_b, {"b.py": "1"})
    repo_tech_store.record_repo_scan("demo-project", str(repo_b))

    with sqlite3.connect(isolated_repo_tech_store) as conn:
        rows = conn.execute("SELECT repo_path FROM watched_projects").fetchall()
    assert rows == [(str(repo_b),)]  # one row, updated in place -- not a duplicate


def test_scan_all_watched_projects_rescans_every_registered_project(tmp_path, isolated_repo_tech_store):
    repo_a = tmp_path / "repo_a"
    repo_a.mkdir()
    make_git_repo(repo_a, {"a.py": "1"})
    repo_tech_store.record_repo_scan("project-a", str(repo_a))

    repo_b = tmp_path / "repo_b"
    repo_b.mkdir()
    make_git_repo(repo_b, {"b.js": "1"})
    repo_tech_store.record_repo_scan("project-b", str(repo_b))

    # Add a new file to project-a's repo since its scan, to prove the
    # rescan reflects current state rather than replaying stale results
    (repo_a / "c.sql").write_text("SELECT 1")
    subprocess.run(["git", "add", "-A"], cwd=repo_a, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add sql file"], cwd=repo_a, check=True)

    results = repo_tech_store.scan_all_watched_projects()

    by_project = {r["project"]: r for r in results}
    assert set(by_project) == {"project-a", "project-b"}
    assert by_project["project-a"]["languages"] == [
        {"name": "Python", "file_count": 1},
        {"name": "SQL", "file_count": 1},
    ]
    assert by_project["project-b"]["languages"] == [{"name": "JavaScript", "file_count": 1}]


def test_scan_all_watched_projects_reports_error_for_missing_path_without_aborting(
    tmp_path, isolated_repo_tech_store
):
    repo_a = tmp_path / "repo_a"
    repo_a.mkdir()
    make_git_repo(repo_a, {"a.py": "1"})
    repo_tech_store.record_repo_scan("project-a", str(repo_a))

    missing_path = str(tmp_path / "does-not-exist")
    with sqlite3.connect(isolated_repo_tech_store) as conn:
        conn.execute("INSERT INTO projects (name) VALUES ('project-missing')")
        pid = conn.execute("SELECT id FROM projects WHERE name = 'project-missing'").fetchone()[0]
        conn.execute(
            "INSERT INTO watched_projects (project_id, repo_path) VALUES (?, ?)",
            (pid, missing_path),
        )

    results = repo_tech_store.scan_all_watched_projects()

    by_project = {r["project"]: r for r in results}
    assert "languages" in by_project["project-a"]  # unaffected by the other project's failure
    assert "error" in by_project["project-missing"]


def test_scan_all_watched_projects_empty_when_nothing_registered(isolated_repo_tech_store):
    assert repo_tech_store.scan_all_watched_projects() == []
