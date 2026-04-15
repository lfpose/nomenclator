"""Tests for Worker resume on startup (P08-07)."""

import os
import sqlite3
import tempfile
import time

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
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    return factory


@pytest.mark.asyncio_mode("auto")
async def test_first_tick_runs_immediately_on_start(temp_db, fake_anthropic):
    """First tick should run immediately on worker start, not delayed by tick_interval."""
    import asyncio

    # Create a submitted job with in_progress batch
    conn = sqlite3.connect(temp_db, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")

    job_id = jobs_dao.create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    jobs_dao.update_job_status(conn, job_id, "submitted")
    conn.commit()

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
    conn.commit()
    conn.close()

    # Create worker with long tick_interval (10 seconds)
    db_factory = get_temp_db_factory(temp_db)
    worker = Worker(client=fake_anthropic, db_factory=db_factory, tick_interval=10.0)

    # Start worker and immediately check if tick ran
    start_time = time.time()
    await worker.start()

    # Wait a bit for the tick to complete
    await asyncio.sleep(0.1)

    # Check that tick ran within 1 second (much less than 10 second interval)
    assert time.time() - start_time < 1.0

    # Check that job was polled (transitioned to polling)
    conn2 = sqlite3.connect(temp_db, isolation_level=None)
    conn2.row_factory = sqlite3.Row
    conn2.execute("PRAGMA journal_mode = WAL")
    conn2.execute("PRAGMA foreign_keys = ON")
    job = jobs_dao.get_job(conn2, job_id)
    conn2.close()

    assert job.status == "polling"
    assert worker.last_tick_at > 0

    await worker.stop()


@pytest.mark.asyncio_mode("auto")
async def test_queued_job_on_startup_transitioned_to_failed(temp_db, fake_anthropic):
    """Jobs stuck in 'queued' state on startup should be transitioned to 'failed' with reason 'restart_during_queue'."""
    import asyncio

    # Create a queued job (pathological case: server crashed between insert and submit)
    conn = sqlite3.connect(temp_db, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")

    job_id = jobs_dao.create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    jobs_dao.update_job_status(conn, job_id, "queued")
    conn.commit()
    conn.close()

    # Start worker
    db_factory = get_temp_db_factory(temp_db)
    worker = Worker(client=fake_anthropic, db_factory=db_factory, tick_interval=10.0)
    await worker.start()

    # Wait a bit for the tick to complete
    await asyncio.sleep(0.1)

    # Check that queued job was transitioned to failed
    conn2 = sqlite3.connect(temp_db, isolation_level=None)
    conn2.row_factory = sqlite3.Row
    conn2.execute("PRAGMA journal_mode = WAL")
    conn2.execute("PRAGMA foreign_keys = ON")
    job = jobs_dao.get_job(conn2, job_id)
    conn2.close()

    assert job.status == "failed"

    await worker.stop()


@pytest.mark.asyncio_mode("auto")
async def test_submitted_job_polled_immediately(temp_db, fake_anthropic):
    """Submitted jobs should be polled immediately on worker start."""
    import asyncio

    # Create a submitted job with in_progress batch
    conn = sqlite3.connect(temp_db, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")

    job_id = jobs_dao.create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    jobs_dao.update_job_status(conn, job_id, "submitted")
    conn.commit()

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
    conn.commit()
    conn.close()

    # Start worker
    db_factory = get_temp_db_factory(temp_db)
    worker = Worker(client=fake_anthropic, db_factory=db_factory, tick_interval=10.0)
    await worker.start()

    # Wait a bit for the tick to complete
    await asyncio.sleep(0.1)

    # Check that submitted job was polled
    conn2 = sqlite3.connect(temp_db, isolation_level=None)
    conn2.row_factory = sqlite3.Row
    conn2.execute("PRAGMA journal_mode = WAL")
    conn2.execute("PRAGMA foreign_keys = ON")
    job = jobs_dao.get_job(conn2, job_id)
    batch = batches_dao.get_batch(conn2, batch_id)
    conn2.close()

    # Job should be in polling state after first poll
    assert job.status == "polling"
    # Batch should have been polled
    assert batch.polled_at is not None
    assert worker.last_tick_at > 0

    await worker.stop()
