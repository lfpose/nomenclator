"""Tests for Worker.tick() polling behavior."""

import os
import sqlite3
import tempfile
import pytest

from app.db import _apply_migrations
from app.worker.poller import Worker
from app.dao import jobs as jobs_dao, batches as batches_dao


@pytest.fixture
def temp_db():
    """Create a temporary file-based database for testing.

    File-based DB allows multiple connections to the same database,
    which is needed because worker.tick() closes connections.
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Create and initialize DB
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    _apply_migrations(conn)
    conn.close()

    yield path

    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


def get_temp_db_factory(path):
    """Factory function that returns a fresh connection to temp database."""
    def factory():
        conn = sqlite3.connect(path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn
    return factory


def test_tick_ignores_terminal_jobs(temp_db, fake_anthropic):
    """tick() should skip jobs in terminal states."""
    conn = sqlite3.connect(temp_db, isolation_level=None)
    conn.row_factory = sqlite3.Row

    # Create a completed job
    job_id = jobs_dao.create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    jobs_dao.update_job_status(conn, job_id, "completed")

    # Create a batch for job (in ended state)
    batches_dao.insert_batch(
        conn,
        id="batch_1",
        job_id=job_id,
        retry_round=0,
        parent_batch_id=None,
        status="ended",
        request_count=1,
    )
    conn.close()

    # Create a worker and tick
    db_factory = get_temp_db_factory(temp_db)
    worker = Worker(client=fake_anthropic, db_factory=db_factory)
    import asyncio
    asyncio.run(worker.tick())

    # Check state with new connection
    conn2 = sqlite3.connect(temp_db, isolation_level=None)
    conn2.row_factory = sqlite3.Row
    job = jobs_dao.get_job(conn2, job_id)
    conn2.close()

    assert job.status == "completed"


def test_tick_polls_submitted_jobs_and_transitions_to_polling(temp_db, fake_anthropic):
    """tick() should poll submitted jobs and transition to polling state."""
    conn = sqlite3.connect(temp_db, isolation_level=None)
    conn.row_factory = sqlite3.Row

    # Create a submitted job with an in_progress batch
    job_id = jobs_dao.create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    jobs_dao.update_job_status(conn, job_id, "submitted")

    # Submit a batch to fake Anthropic
    batch_id = fake_anthropic.submit_batch([{"custom_id": "req1", "params": {}}])

    # Record batch in DB
    batches_dao.insert_batch(
        conn,
        id=batch_id,
        job_id=job_id,
        retry_round=0,
        parent_batch_id=None,
        status="in_progress",
        request_count=1,
    )
    conn.close()

    # Tick the worker
    db_factory = get_temp_db_factory(temp_db)
    worker = Worker(client=fake_anthropic, db_factory=db_factory)
    import asyncio
    asyncio.run(worker.tick())

    # Check state with new connection
    conn2 = sqlite3.connect(temp_db, isolation_level=None)
    conn2.row_factory = sqlite3.Row
    job = jobs_dao.get_job(conn2, job_id)
    conn2.close()

    assert job.status == "polling"


def test_tick_updates_batch_polled_at(temp_db, fake_anthropic):
    """tick() should update polled_at timestamp on batches."""
    conn = sqlite3.connect(temp_db, isolation_level=None)
    conn.row_factory = sqlite3.Row

    # Create a submitted job with in_progress batch
    job_id = jobs_dao.create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    jobs_dao.update_job_status(conn, job_id, "submitted")

    batch_id = fake_anthropic.submit_batch([{"custom_id": "req1", "params": {}}])
    batches_dao.insert_batch(
        conn,
        id=batch_id,
        job_id=job_id,
        retry_round=0,
        parent_batch_id=None,
        status="in_progress",
        request_count=1,
    )
    conn.close()

    # Tick the worker
    import asyncio
    import time
    db_factory = get_temp_db_factory(temp_db)
    worker = Worker(client=fake_anthropic, db_factory=db_factory)
    before_tick = int(time.time())
    asyncio.run(worker.tick())
    after_tick = int(time.time())

    # Check state with new connection
    conn2 = sqlite3.connect(temp_db, isolation_level=None)
    conn2.row_factory = sqlite3.Row
    batch = batches_dao.get_batch(conn2, batch_id)
    conn2.close()

    assert batch.polled_at is not None
    assert before_tick <= batch.polled_at <= after_tick


def test_tick_skips_already_ended_batches(temp_db, fake_anthropic):
    """tick() should skip batches that are already ended/canceled/expired."""
    conn = sqlite3.connect(temp_db, isolation_level=None)
    conn.row_factory = sqlite3.Row

    # Create a submitted job with an already-ended batch
    job_id = jobs_dao.create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    jobs_dao.update_job_status(conn, job_id, "submitted")

    batch_id = fake_anthropic.submit_batch([{"custom_id": "req1", "params": {}}])
    fake_anthropic.complete_batch(batch_id, [])  # Mark as ended

    batches_dao.insert_batch(
        conn,
        id=batch_id,
        job_id=job_id,
        retry_round=0,
        parent_batch_id=None,
        status="ended",
        request_count=1,
    )
    conn.close()

    # Tick the worker - should not try to get_batch_status on ended batch
    db_factory = get_temp_db_factory(temp_db)
    worker = Worker(client=fake_anthropic, db_factory=db_factory)
    import asyncio
    asyncio.run(worker.tick())

    # Check state with new connection
    conn2 = sqlite3.connect(temp_db, isolation_level=None)
    conn2.row_factory = sqlite3.Row
    batch = batches_dao.get_batch(conn2, batch_id)
    conn2.close()

    assert batch.status == "ended"
    # polled_at should remain None (we didn't poll it)
    assert batch.polled_at is None
