import pytest

from app.dao.task_templates import get_template, TaskTemplate
from app.db import _apply_migrations


@pytest.fixture
def conn():
    """Create a fresh in-memory SQLite connection with migrations applied."""
    import sqlite3
    c = sqlite3.connect(":memory:", isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode = WAL")
    c.execute("PRAGMA foreign_keys = ON")
    _apply_migrations(c)
    yield c
    c.close()


def test_get_template_returns_seed_row(conn):
    """Test that get_template returns the seeded job_titles_es template."""
    template = get_template(conn, "job_titles_es")
    assert template is not None
    assert template.id == "job_titles_es"
    assert template.name == "Spanish job title standardizer"
    assert template.system_prompt == "PLACEHOLDER"
    assert template.few_shots == []
    assert template.output_columns == ["male_es", "female_es", "category"]
    assert template.default_titles_per_request == 25


def test_get_template_nonexistent_returns_none(conn):
    """Test that get_template returns None for a nonexistent template ID."""
    template = get_template(conn, "nonexistent_template")
    assert template is None


def test_get_template_parses_json_fields(conn):
    """Test that get_template correctly parses JSON fields."""
    # Insert a test template with JSON fields
    conn.execute(
        """
        INSERT INTO task_templates 
        (id, name, system_prompt, few_shots, output_columns, default_titles_per_request, created_at)
        VALUES (?, ?, ?, ?, ?, ?, unixepoch())
        """,
        (
            "test_template",
            "Test Template",
            "Test prompt",
            '[{"input": "test", "output": "result"}]',
            '["col1", "col2", "col3"]',
            10,
        )
    )
    
    template = get_template(conn, "test_template")
    assert template is not None
    assert isinstance(template.few_shots, list)
    assert len(template.few_shots) == 1
    assert template.few_shots[0] == {"input": "test", "output": "result"}
    assert isinstance(template.output_columns, list)
    assert template.output_columns == ["col1", "col2", "col3"]
