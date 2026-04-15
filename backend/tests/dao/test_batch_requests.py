import pytest

from app.dao.batch_requests import BatchRequest, insert_request, list_requests_for_batch, mark_request_completed, mark_request_failed, mark_request_missing, list_pending_requests
from app.dao.batches import insert_batch
from app.dao.jobs import create_job
import uuid


def test_insert_serializes_cluster_ids_as_json(conn):
    """Test that insert_request serializes cluster_ids as JSON."""
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
        request_count=2,
    )

    insert_request(
        conn,
        id="req-1",
        batch_id="batch-123",
        cluster_ids=[1, 2, 3, 4, 5],
    )

    # Verify JSON serialization in database
    row = conn.execute("SELECT cluster_ids FROM batch_requests WHERE id = ?", ("req-1",)).fetchone()
    assert row["cluster_ids"] == "[1, 2, 3, 4, 5]"

    # Verify deserialization
    requests = list_requests_for_batch(conn, batch_id="batch-123")
    assert len(requests) == 1
    assert requests[0].cluster_ids == [1, 2, 3, 4, 5]


def test_list_requests_deserializes_cluster_ids(conn):
    """Test that list_requests_for_batch deserializes cluster_ids correctly."""
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
        request_count=3,
    )

    insert_request(
        conn,
        id="req-1",
        batch_id="batch-123",
        cluster_ids=[1, 2],
    )
    insert_request(
        conn,
        id="req-2",
        batch_id="batch-123",
        cluster_ids=[3],
    )
    insert_request(
        conn,
        id="req-3",
        batch_id="batch-123",
        cluster_ids=[4, 5, 6],
    )

    requests = list_requests_for_batch(conn, batch_id="batch-123")
    assert len(requests) == 3
    assert requests[0].cluster_ids == [1, 2]
    assert requests[1].cluster_ids == [3]
    assert requests[2].cluster_ids == [4, 5, 6]
    assert all(req.status == "pending" for req in requests)


def test_mark_request_completed_updates_status(conn):
    """Test that mark_request_completed updates status and raw_response."""
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
        request_count=1,
    )

    insert_request(
        conn,
        id="req-1",
        batch_id="batch-123",
        cluster_ids=[1, 2],
    )

    mark_request_completed(conn, request_id="req-1", raw_response='{"results": [...]}'  )

    requests = list_requests_for_batch(conn, batch_id="batch-123")
    assert len(requests) == 1
    assert requests[0].status == "completed"
    assert requests[0].raw_response == '{"results": [...]}'
    assert requests[0].error is None


def test_mark_request_failed_sets_error(conn):
    """Test that mark_request_failed sets error and status."""
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
        request_count=1,
    )

    insert_request(
        conn,
        id="req-1",
        batch_id="batch-123",
        cluster_ids=[1, 2],
    )

    mark_request_failed(conn, request_id="req-1", error="timeout")

    requests = list_requests_for_batch(conn, batch_id="batch-123")
    assert len(requests) == 1
    assert requests[0].status == "failed"
    assert requests[0].error == "timeout"
    assert requests[0].raw_response is None


def test_list_pending_requests_filters_by_status(conn):
    """Test that list_pending_requests returns only pending requests."""
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
        request_count=5,
    )

    insert_request(
        conn,
        id="req-1",
        batch_id="batch-123",
        cluster_ids=[1],
    )
    insert_request(
        conn,
        id="req-2",
        batch_id="batch-123",
        cluster_ids=[2],
    )
    insert_request(
        conn,
        id="req-3",
        batch_id="batch-123",
        cluster_ids=[3],
    )
    insert_request(
        conn,
        id="req-4",
        batch_id="batch-123",
        cluster_ids=[4],
    )
    insert_request(
        conn,
        id="req-5",
        batch_id="batch-123",
        cluster_ids=[5],
    )

    # Mark some as completed/failed/missing
    mark_request_completed(conn, request_id="req-1", raw_response='{"results": []}')
    mark_request_failed(conn, request_id="req-2", error="timeout")
    mark_request_missing(conn, request_id="req-3")

    # Only req-4 and req-5 should be pending
    pending = list_pending_requests(conn, batch_id="batch-123")
    assert len(pending) == 2
    assert all(req.status == "pending" for req in pending)
    assert set(req.id for req in pending) == {"req-4", "req-5"}
