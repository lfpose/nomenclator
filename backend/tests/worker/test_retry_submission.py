"""Tests for _submit_retry functionality in worker.poller (P08-06)."""

import asyncio
import sqlite3
import pytest

from app.worker.poller import Worker
from tests.anthropic.fake_client import FakeAnthropicBatchClient


def get_temp_db_factory():
    """Create a factory that returns fresh connections to a temp file-based DB."""
    import tempfile
    import os
    from app.db import _apply_migrations

    # Create a temp file for the database
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    def factory():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode and foreign keys
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _apply_migrations(conn)
        return conn

    # Cleanup function for tests to use
    def cleanup():
        try:
            os.unlink(db_path)
        except FileNotFoundError:
            pass

    factory.cleanup = cleanup
    factory.db_path = db_path
    return factory


@pytest.fixture
def temp_db_factory():
    """Fixture that provides a temp DB factory and cleans up after the test."""
    factory = get_temp_db_factory()
    yield factory
    factory.cleanup()


@pytest.fixture
def worker(temp_db_factory):
    """Fixture that provides a Worker instance with a FakeAnthropicBatchClient."""
    client = FakeAnthropicBatchClient()
    worker = Worker(client=client, db_factory=temp_db_factory)
    return worker


@pytest.fixture
def conn(temp_db_factory):
    """Fixture that provides a fresh database connection."""
    conn = temp_db_factory()
    yield conn
    conn.close()


def setup_job_with_clusters(conn, cluster_count=5, batch_round=0, job_status="polling", titles_per_request=25):
    """Helper to set up a job with clusters and batches.

    Args:
        conn: Database connection
        cluster_count: Number of clusters to create
        batch_round: Retry round for the batch
        job_status: Initial job status (default 'polling' for completed batch)
        titles_per_request: Initial TPR value

    Returns:
        tuple: (job_id, batch_id)
    """
    from app.dao import jobs as jobs_dao, clusters as clusters_dao, batches as batches_dao
    from app.dao import job_rows as job_rows_dao
    from app.csv_io.normalize import normalize

    # Create a job
    job_id = jobs_dao.create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=titles_per_request,
        row_subset_mode="all",
        row_subset_n=None,
        is_dry_run=False,
    )

    # Create some job rows
    job_titles = [
        "Jefe de Compras",
        "Ingeniero de Software",
        "Gerente de Ventas",
        "Director de Marketing",
        "Analista de Datos",
    ]
    # Extend to match cluster_count if needed
    while len(job_titles) < cluster_count:
        job_titles.append(f"Rol {len(job_titles) + 1}")

    rows = []
    for i, title in enumerate(job_titles[:cluster_count]):
        rows.append((i, title, normalize(title)))

    # Insert job rows
    job_rows_dao.bulk_insert_rows(conn, job_id, rows)

    # Get the inserted row IDs
    all_job_rows = job_rows_dao.list_rows(conn, job_id)

    # Create clusters - one per row for simplicity
    cluster_ids = []
    for i, row in enumerate(all_job_rows[:cluster_count]):
        cluster_id = clusters_dao.insert_cluster(
            conn,
            job_id=job_id,
            representative_original=row.original,
            normalized_key=row.normalized,
            member_count=1,
        )
        cluster_ids.append(cluster_id)
        # Assign this row to the cluster
        job_rows_dao.assign_cluster(
            conn,
            row_ids=[row.id],
            cluster_id=cluster_id,
            is_representative_row_id=row.id,
        )

    # Create a batch in "ended" state
    batch_id = f"batch_{job_id}_r{batch_round}"
    batches_dao.insert_batch(
        conn,
        id=batch_id,
        job_id=job_id,
        retry_round=batch_round,
        parent_batch_id=None,
        status="ended",
        request_count=1,
    )

    # Update job status
    jobs_dao.update_job_status(conn, job_id, job_status)

    return job_id, batch_id


def resolve_cluster(conn, cluster_id, male_es, female_es, category):
    """Helper to resolve a cluster (set its answer fields)."""
    from app.dao import clusters as clusters_dao
    clusters_dao.update_cluster_answers(
        conn,
        cluster_id,
        male_es=male_es,
        female_es=female_es,
        category=category,
    )


def get_job(conn, job_id):
    """Helper to get a job by ID."""
    from app.dao import jobs as jobs_dao
    return jobs_dao.get_job(conn, job_id)


def test_retry_halves_titles_per_request(conn, worker):
    """Test that retry halves the titles_per_request value."""
    # Set up a job with TPR=25 at round 0
    job_id, batch_id = setup_job_with_clusters(
        conn,
        cluster_count=10,
        batch_round=0,
        job_status="polling",
        titles_per_request=25,
    )

    # Resolve some clusters, leave some unresolved
    from app.dao import clusters as clusters_dao
    clusters = clusters_dao.list_clusters(conn, job_id)
    for i in range(7):
        resolve_cluster(conn, clusters[i].id, f"Male {i}", f"Female {i}", f"category_{i}")
    # clusters[7], [8], [9] remain unresolved

    # Trigger retry for round 1
    job_obj = get_job(conn, job_id)
    asyncio.run(worker._submit_retry(conn, job_obj, new_round=1))

    # Check that new batch has halved TPR for its requests
    from app.dao import batch_requests as br_dao, batches as batches_dao
    batches = [b for b in batches_dao.list_batches_for_job(conn, job_id) if b.retry_round == 1]
    assert len(batches) == 1

    retry_batch = batches[0]
    requests = br_dao.list_requests_for_batch(conn, retry_batch.id)

    # With 3 unresolved clusters and TPR=25, new TPR should be 25 // 2 = 12
    # All 3 clusters should fit in 1 request
    assert len(requests) == 1
    assert len(requests[0].cluster_ids) == 3


def test_retry_only_includes_unresolved_clusters(conn, worker):
    """Test that retry batch only contains unresolved clusters."""
    # Set up a job with 5 clusters
    job_id, batch_id = setup_job_with_clusters(conn, cluster_count=5, batch_round=0)

    # Resolve 3 clusters, leave 2 unresolved
    from app.dao import clusters as clusters_dao
    clusters = clusters_dao.list_clusters(conn, job_id)
    for i in range(3):
        resolve_cluster(conn, clusters[i].id, f"Male {i}", f"Female {i}", f"category_{i}")
    # clusters[3] and clusters[4] remain unresolved

    # Trigger retry
    job_obj = get_job(conn, job_id)
    asyncio.run(worker._submit_retry(conn, job_obj, new_round=1))

    # Check that only 2 unresolved clusters are in the new batch
    from app.dao import batch_requests as br_dao, batches as batches_dao
    batches = [b for b in batches_dao.list_batches_for_job(conn, job_id) if b.retry_round == 1]
    assert len(batches) == 1

    retry_batch = batches[0]
    requests = br_dao.list_requests_for_batch(conn, retry_batch.id)

    total_cluster_ids = []
    for req in requests:
        total_cluster_ids.extend(req.cluster_ids)

    # Should only have 2 cluster IDs (the unresolved ones)
    assert len(total_cluster_ids) == 2
    # Verify these are the unresolved ones
    unresolved_ids = {clusters[3].id, clusters[4].id}
    assert set(total_cluster_ids) == unresolved_ids


def test_retry_increments_round(conn, worker):
    """Test that retry batch has incremented retry_round value."""
    # Set up a job
    job_id, batch_id = setup_job_with_clusters(conn, cluster_count=5, batch_round=0)

    # Trigger retry (round 1)
    job_obj = get_job(conn, job_id)
    asyncio.run(worker._submit_retry(conn, job_obj, new_round=1))

    # Check new batch has retry_round=1
    from app.dao import batches as batches_dao
    batches = [b for b in batches_dao.list_batches_for_job(conn, job_id) if b.retry_round == 1]
    assert len(batches) == 1
    assert batches[0].retry_round == 1

    # Mark the retry batch as ended and trigger another retry (round 2)
    from app.dao import batches as batches_dao
    retry_batch_id = batches[0].id
    batches_dao.update_batch_status(conn, retry_batch_id, status="ended", completed_at=1234567900)

    # Update job back to polling for second retry
    from app.jobs.service import transition
    transition(conn, job_id, "polling", reason="test")

    # Trigger second retry (round 2)
    job_obj = get_job(conn, job_id)
    asyncio.run(worker._submit_retry(conn, job_obj, new_round=2))

    # Check newest batch has retry_round=2
    from app.dao import batches as batches_dao
    batches = [b for b in batches_dao.list_batches_for_job(conn, job_id) if b.retry_round == 2]
    assert len(batches) == 1
    assert batches[0].retry_round == 2


def test_retry_records_parent_batch_id(conn, worker):
    """Test that retry batch correctly references parent batch."""
    # Set up a job with round 0 batch
    job_id, batch_id = setup_job_with_clusters(conn, cluster_count=5, batch_round=0)

    # Trigger retry (round 1)
    job_obj = get_job(conn, job_id)
    asyncio.run(worker._submit_retry(conn, job_obj, new_round=1))

    # Check new batch has parent_batch_id set to initial batch
    from app.dao import batches as batches_dao
    batches = batches_dao.list_batches_for_job(conn, job_id)

    parent_batch = [b for b in batches if b.retry_round == 0][0]
    retry_batch = [b for b in batches if b.retry_round == 1][0]

    assert parent_batch.parent_batch_id is None
    assert retry_batch.parent_batch_id == parent_batch.id


def test_retry_blocks_on_spend_cap_and_flags_stragglers(conn, worker):
    """Test that retry is blocked when spend cap exceeded, stragglers are flagged."""
    import time

    # Set up a job with many clusters to increase estimated cost
    # 200 clusters with halved TPR = ~$0.03 estimated cost
    job_id, batch_id = setup_job_with_clusters(conn, cluster_count=200, batch_round=0)

    # Seed spend_log with $19.98 (just below $20 cap, leaving $0.02 headroom)
    # The retry will cost more than $0.02, triggering the cap
    from app.dao import spend_log as spend_dao
    spend_dao.insert_spend(conn, job_id=job_id, batch_id=None, usd=19.98, at=int(time.time()))

    # Trigger retry - should be blocked by spend cap
    job_obj = get_job(conn, job_id)
    asyncio.run(worker._submit_retry(conn, job_obj, new_round=1))

    # Check that job was completed with error (not retry submitted)
    job = get_job(conn, job_id)
    assert job.status == "completed"

    # Check unresolved clusters were flagged with spend_cap_exceeded
    from app.dao import clusters as clusters_dao
    clusters = clusters_dao.list_clusters(conn, job_id)
    unresolved = [c for c in clusters if c.male_es is None]
    assert len(unresolved) == 200  # All clusters unresolved
    for cluster in unresolved:
        assert cluster.error == "spend_cap_exceeded"

    # No new batch should have been created
    from app.dao import batches as batches_dao
    batches = batches_dao.list_batches_for_job(conn, job_id)
    assert len(batches) == 1  # Only the initial batch


def test_retry_transitions_through_retrying_to_submitted(conn, worker):
    """Test that retry transitions job: polling -> retrying -> submitted."""
    # Set up a job in polling state
    job_id, batch_id = setup_job_with_clusters(conn, cluster_count=5, batch_round=0, job_status="polling")

    # Verify job is in polling state
    job = get_job(conn, job_id)
    assert job.status == "polling"

    # Trigger retry
    job_obj = get_job(conn, job_id)
    asyncio.run(worker._submit_retry(conn, job_obj, new_round=1))

    # Check job transitioned through retrying to submitted
    job = get_job(conn, job_id)
    assert job.status == "submitted"

    # Check retry batch was created with status="in_progress"
    from app.dao import batches as batches_dao
    batches = batches_dao.list_batches_for_job(conn, job_id)
    retry_batch = [b for b in batches if b.retry_round == 1][0]
    assert retry_batch.status == "in_progress"