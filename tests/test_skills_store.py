import sqlite3

import pytest

import skills_store


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    """Point skills_store at a throwaway skills dir and db for the test."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    db_path = tmp_path / "data" / "enablement.db"
    monkeypatch.setattr(skills_store, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(skills_store, "DB_PATH", db_path)
    return skills_dir, db_path


def write_skill(skills_dir, filename, **frontmatter_overrides):
    fields = {
        "name": "example-skill",
        "title": "Example Skill",
        "description": "An example.",
        "category": "technical",
        "path": "null",
        "tags": "[example]",
    }
    fields.update(frontmatter_overrides)
    content = (
        "---\n"
        f"name: {fields['name']}\n"
        f"title: {fields['title']}\n"
        f"description: {fields['description']}\n"
        f"category: {fields['category']}\n"
        f"path: {fields['path']}\n"
        f"tags: {fields['tags']}\n"
        "---\n"
        "# Body\n\nFull content here.\n"
    )
    (skills_dir / filename).write_text(content)


def test_load_all_skills_parses_frontmatter_and_body(isolated_store):
    skills_dir, _ = isolated_store
    write_skill(skills_dir, "example-skill.md")

    skills = skills_store.load_all_skills()

    assert len(skills) == 1
    skill = skills[0]
    assert skill["name"] == "example-skill"
    assert skill["title"] == "Example Skill"
    assert skill["category"] == "technical"
    assert skill["path"] is None
    assert skill["tags"] == ["example"]
    assert "Full content here." in skill["body"]
    assert not skill["body"].startswith("\n")


def test_load_all_skills_empty_dir_returns_empty_list(isolated_store):
    assert skills_store.load_all_skills() == []


def test_find_skill_returns_match(isolated_store):
    skills_dir, _ = isolated_store
    write_skill(skills_dir, "a.md", name="skill-a", title="A")
    write_skill(skills_dir, "b.md", name="skill-b", title="B")

    found = skills_store.find_skill("skill-b")

    assert found is not None
    assert found["title"] == "B"


def test_find_skill_returns_none_when_missing(isolated_store):
    skills_dir, _ = isolated_store
    write_skill(skills_dir, "a.md", name="skill-a")

    assert skills_store.find_skill("does-not-exist") is None


def test_parse_skill_file_without_frontmatter_raises(isolated_store):
    skills_dir, _ = isolated_store
    (skills_dir / "broken.md").write_text("# No frontmatter here\n")

    with pytest.raises(ValueError):
        skills_store.load_all_skills()


def test_init_db_creates_table(isolated_store):
    _, db_path = isolated_store

    skills_store.init_db()

    assert db_path.exists()
    with sqlite3.connect(db_path) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='skill_usage'"
        ).fetchall()
    assert tables == [("skill_usage",)]


def test_log_usage_inserts_row(isolated_store):
    skills_store.init_db()

    skills_store.log_usage("example-skill", "listed")
    skills_store.log_usage("example-skill", "fetched")

    with sqlite3.connect(skills_store.DB_PATH) as conn:
        rows = conn.execute(
            "SELECT skill_name, action FROM skill_usage ORDER BY id"
        ).fetchall()
    assert rows == [
        ("example-skill", "listed"),
        ("example-skill", "fetched"),
    ]


def test_init_db_creates_library_snapshots_table(isolated_store):
    skills_store.init_db()

    with sqlite3.connect(skills_store.DB_PATH) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='library_snapshots'"
        ).fetchall()
    assert tables == [("library_snapshots",)]


def test_log_usage_stores_chars_and_tokens_est(isolated_store):
    skills_store.init_db()

    skills_store.log_usage("example-skill", "fetched", chars=400, tokens_est=100)

    with sqlite3.connect(skills_store.DB_PATH) as conn:
        row = conn.execute(
            "SELECT chars, tokens_est FROM skill_usage WHERE skill_name = 'example-skill'"
        ).fetchone()
    assert row == (400, 100)


def test_migration_is_additive_and_preserves_old_rows(isolated_store):
    """Simulates a pre-Session-6 database (skill_usage with no size columns,
    holding a real historical row) and confirms init_db() adds the columns
    without touching that row."""
    _, db_path = isolated_store
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE skill_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_name TEXT NOT NULL,
                action TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            "INSERT INTO skill_usage (skill_name, action, created_at) "
            "VALUES ('historical-skill', 'fetched', '2020-01-01 00:00:00')"
        )
        conn.commit()

    skills_store.init_db()

    with sqlite3.connect(db_path) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(skill_usage)")]
        row = conn.execute(
            "SELECT skill_name, action, chars, tokens_est FROM skill_usage"
        ).fetchall()
    assert "chars" in columns
    assert "tokens_est" in columns
    assert row == [("historical-skill", "fetched", None, None)]


def test_init_db_is_idempotent_across_repeated_calls(isolated_store):
    skills_store.init_db()
    skills_store.init_db()
    skills_store.init_db()

    with sqlite3.connect(skills_store.DB_PATH) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(skill_usage)")]
    assert columns.count("chars") == 1
    assert columns.count("tokens_est") == 1


def test_measure_listing_sizes_one_skills_metadata(isolated_store):
    skills_dir, _ = isolated_store
    write_skill(skills_dir, "example-skill.md")
    skill = skills_store.load_all_skills()[0]

    chars, tokens_est = skills_store.measure_listing(skill)

    assert chars > 0
    assert tokens_est == chars // 4


def test_record_library_snapshot_dedups_when_unchanged(isolated_store):
    skills_dir, _ = isolated_store
    write_skill(skills_dir, "a.md", name="skill-a")
    skills_store.init_db()

    skills_store.record_library_snapshot()
    skills_store.record_library_snapshot()
    skills_store.record_library_snapshot()

    with sqlite3.connect(skills_store.DB_PATH) as conn:
        count = conn.execute("SELECT COUNT(*) FROM library_snapshots").fetchone()[0]
    assert count == 1


def test_record_library_snapshot_inserts_new_row_when_library_changes(isolated_store):
    skills_dir, _ = isolated_store
    write_skill(skills_dir, "a.md", name="skill-a")
    skills_store.init_db()
    skills_store.record_library_snapshot()

    write_skill(skills_dir, "b.md", name="skill-b")
    skills_store.record_library_snapshot()

    with sqlite3.connect(skills_store.DB_PATH) as conn:
        snapshots = conn.execute(
            "SELECT total_skills FROM library_snapshots ORDER BY id"
        ).fetchall()
    assert snapshots == [(1,), (2,)]
