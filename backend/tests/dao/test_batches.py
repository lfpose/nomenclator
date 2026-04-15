import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def conn():
    """Create an in-memory SQLite connection with all migrations applied."""
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    # Apply migrations
    migrations_dir = Path(__file__).parent.parent.parent / "app" / "migrations"
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at INTEGER NOT NULL
        )
    """)

    for path in sorted(migrations_dir.glob("*.sql")):
        version = int(path.name.split("_")[0])
        if conn.execute("SELECT 1 FROM schema_version WHERE version = ?", (version,)).fetchone():
            continue
        sql = path.read_text()
        conn.executescript(sql)
        conn.execute("INSERT INTO schema_version VALUES (?, unixepoch())", (version,))

    yield conn
    conn.close()


def test_insert_and_get_roundtrips(conn):
    """Test that insert_batch and get_batch roundtrip correctly."""
    from backend.app.dao.batches import get_batch, insert_batch
    from backend.app.dao.jobs import create_job

    job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )

    insert_batch(
        conn,
        id="batch-123",
        job_id=job_id,
        retry_round=0,
        parent_batch_id=None,
        status="in_progress",
        request_count=10,
    )

    batch = get_batch(conn, batch_id="batch-123")
    assert batch is not None
    assert batch.id == "batch-123"
    assert batch.job_id == job_id
    assert batch.retry_round == 0
    assert batch.parent_batch_id is None
    assert batch.status == "in_progress"
    assert batch.request_count == 10
    assert batch.polled_at is None
    assert batch.completed_at is None
    assert batch.submitted_at is not None


def test_update_batch_status_sets_timestamps(conn):
    """Test that update_batch_status sets polled_at and completed_at when provided."""
    from backend.app.dao.batches import get_batch, insert_batch, update_batch_status
    from backend.app.dao.jobs import create_job

    job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )

    insert_batch(
        conn,
        id="batch-123",
        job_id=job_id,
        retry_round=0,
        parent_batch_id=None,
        status="in_progress",
        request_count=10,
    )

    # Update with polled_at
    update_batch_status(conn, batch_id="batch-123", status="processing", polled_at=1234567890)

    batch = get_batch(conn, batch_id="batch-123")
    assert batch is not None
    assert batch.status == "processing"
    assert batch.polled_at == 1234567890
    assert batch.completed_at is None

    # Update with completed_at
    update_batch_status(
        conn, batch_id="batch-123", status="succeeded", completed_at=1234567900
    )

    batch = get_batch(conn, batch_id="batch-123")
    assert batch is not None
    assert batch.status == "succeeded"
    assert batch.completed_at == 1234567900


def test_list_batches_for_job_ordered_by_round(conn):
    """Test that list_batches_for_job returns batches ordered by retry_round ASC."""
    from backend.app.dao.batches import insert_batch, list_batches_for_job
    from backend.app.dao.jobs import create_job

    job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )

    insert_batch(
        conn,
        id="batch-3",
        job_id=job_id,
        retry_round=2,
        parent_batch_id=None,
        status="in_progress",
        request_count=5,
    )
    insert_batch(
        conn,
        id="batch-1",
        job_id=job_id,
        retry_round=0,
        parent_batch_id=None,
        status="completed",
        request_count=10,
    )
    insert_batch(
        conn,
        id="batch-2",
        job_id=job_id,
        retry_round=1,
        parent_batch_id="batch-1",
        status="in_progress",
        request_count=3,
    )

    batches = list_batches_for_job(conn, job_id=job_id)
    assert len(batches) == 3
    assert batches[0].id == "batch-1"
    assert batches[0].retry_round == 0
    assert batches[1].id == "batch-2"
    assert batches[1].retry_round == 1
    assert batches[2].id == "batch-3"
    assert batches[2].retry_round == 2


def test_list_non_terminal_batches_excludes_completed_jobs(conn):
    """Test that list_non_terminal_batches excludes batches from completed/failed/cancelled jobs."""
    from backend.app.dao.batches import insert_batch, list_non_terminal_batches
    from backend.app.dao.jobs import create_job, update_job_status

    # Create a job in non-terminal status
    active_job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    update_job_status(conn, active_job_id, "submitted")

    insert_batch(
        conn,
        id="batch-active",
        job_id=active_job_id,
        retry_round=0,
        parent_batch_id=None,
        status="in_progress",
        request_count=10,
    )

    # Create a completed job
    completed_job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    update_job_status(conn, completed_job_id, "completed")

    insert_batch(
        conn,
        id="batch-completed",
        job_id=completed_job_id,
        retry_round=0,
        parent_batch_id=None,
        status="succeeded",
        request_count=5,
    )

    # Create a failed job
    failed_job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    update_job_status(conn, failed_job_id, "failed")

    insert_batch(
        conn,
        id="batch-failed",
        job_id=failed_job_id,
        retry_round=0,
        parent_batch_id=None,
        status="errored",
        request_count=3,
    )

    # Create a cancelled job
    cancelled_job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    update_job_status(conn, cancelled_job_id, "cancelled")

    insert_batch(
        conn,
        id="batch-cancelled",
        job_id=cancelled_job_id,
        retry_round=0,
        parent_batch_id=None,
        status="cancelled",
        request_count=2,
    )

    batches = list_non_terminal_batches(conn)
    assert len(batches) == 1
    assert batches[0].id == "batch-active"
