"""Tests for commit_job function in jobs/service.py."""

import time

import pytest

from app.csv_io.ingest import ingest
from app.dao import batches as batches_dao
from app.dao import batch_requests as batch_requests_dao
from app.dao import clusters as clusters_dao
from app.dao import jobs as jobs_dao
from app.dao import spend_log as spend_log_dao
from app.jobs.service import (
    ConcurrencyError,
    SpendCapExceeded,
    commit_job,
    create_preview_job,
)


def test_commit_builds_batch_requests(conn, fake_anthropic):
    """Verify that commit_job builds batch requests correctly."""
    # Create a preview job with enough clusters for multiple requests
    rows = ingest(text="Jefe de Compras\nJefe Compras\nJefe de compras\nIngeniero de Software\nIngeniero Software\nGerente de Producto\nGerente Producto\nVP de Ventas\nVicepresidente de Ventas\nDirector de Finanzas\nDirector Finanzas\nContador General\nContador")
    threshold = 90
    titles_per_request = 3

    # Create preview job
    preview = create_preview_job(
        conn,
        text="\n".join(r[1] for r in rows),
        threshold=threshold,
        titles_per_request=titles_per_request,
    )

    # Commit the job
    commit_job(conn, fake_anthropic, preview.job_id, taxonomy=None)

    # Verify batch was submitted
    batches = batches_dao.list_batches_for_job(conn, preview.job_id)
    assert len(batches) == 1
    batch = batches[0]
    assert batch.status == "in_progress"
    assert batch.retry_round == 0
    assert batch.parent_batch_id is None

    # Verify requests were built
    requests = batch_requests_dao.list_requests_for_batch(conn, batch.id)
    assert len(requests) > 0

    # Verify fake client received the requests
    fake_batch = fake_anthropic.batches[batch.id]
    assert len(fake_batch.requests) == len(requests)


def test_commit_transitions_to_submitted(conn, fake_anthropic):
    """Verify that commit_job transitions job to submitted state."""
    rows = ingest(text="Jefe de Compras\nJefe Compras\nIngeniero de Software\nGerente de Producto")
    preview = create_preview_job(
        conn,
        text="\n".join(r[1] for r in rows),
        threshold=90,
        titles_per_request=25,
    )

    commit_job(conn, fake_anthropic, preview.job_id)

    # Verify job is in submitted state
    job = jobs_dao.get_job(conn, preview.job_id)
    assert job is not None
    assert job.status == "submitted"


def test_commit_raises_on_non_preview_state(conn, fake_anthropic):
    """Verify that commit_job raises ValueError for non-preview jobs."""
    rows = ingest(text="Jefe de Compras\nJefe Compras")
    preview = create_preview_job(
        conn,
        text="\n".join(r[1] for r in rows),
        threshold=90,
        titles_per_request=25,
    )

    # Transition job to cancelled (valid transition from preview)
    from app.jobs.service import transition
    transition(conn, preview.job_id, "cancelled", reason="test")

    # Try to commit - should raise
    with pytest.raises(ValueError, match="invalid_state"):
        commit_job(conn, fake_anthropic, preview.job_id)


def test_commit_raises_on_spend_cap_exceeded(conn, fake_anthropic):
    """Verify that commit_job raises SpendCapExceeded when cap would be exceeded."""
    rows = ingest(text="Jefe de Compras\nJefe Compras")
    preview = create_preview_job(
        conn,
        text="\n".join(r[1] for r in rows),
        threshold=90,
        titles_per_request=25,
    )

    # Create another completed job to use up spend cap
    # Use $19.997 to leave almost no room (cap is $20.00)
    job_id2 = jobs_dao.create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    spend_log_dao.insert_spend(conn, job_id=job_id2, batch_id=None, usd=19.997, at=int(time.time()))

    # Try to commit - should raise SpendCapExceeded
    with pytest.raises(SpendCapExceeded, match="Monthly cap"):
        commit_job(conn, fake_anthropic, preview.job_id)


def test_commit_raises_on_concurrent_job(conn, fake_anthropic):
    """Verify that commit_job raises ConcurrencyError when another job is running."""
    rows = ingest(text="Jefe de Compras\nJefe Compras")
    preview = create_preview_job(
        conn,
        text="\n".join(r[1] for r in rows),
        threshold=90,
        titles_per_request=25,
    )

    # Create another job in a non-terminal state
    job_id2 = jobs_dao.create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    jobs_dao.update_job_status(conn, job_id2, "queued")

    # Try to commit - should raise ConcurrencyError
    with pytest.raises(ConcurrencyError, match="job_already_running"):
        commit_job(conn, fake_anthropic, preview.job_id)


def test_commit_persists_batch_and_batch_requests(conn, fake_anthropic):
    """Verify that commit_job correctly persists batch and batch_requests."""
    rows = ingest(text="Jefe de Compras\nJefe Compras\nIngeniero de Software\nGerente de Producto\nVP de Ventas")
    preview = create_preview_job(
        conn,
        text="\n".join(r[1] for r in rows),
        threshold=90,
        titles_per_request=2,
    )

    commit_job(conn, fake_anthropic, preview.job_id)

    # Verify batch was persisted
    batches = batches_dao.list_batches_for_job(conn, preview.job_id)
    assert len(batches) == 1
    batch = batches[0]
    assert batch.job_id == preview.job_id
    assert batch.status == "in_progress"

    # Verify batch_requests were persisted
    requests = batch_requests_dao.list_requests_for_batch(conn, batch.id)
    assert len(requests) > 0
    for req in requests:
        assert req.batch_id == batch.id
        assert req.status == "pending"
        assert isinstance(req.cluster_ids, list)
        assert len(req.cluster_ids) > 0


def test_commit_persists_cluster_ids_json(conn, fake_anthropic):
    """Verify that commit_job correctly serializes cluster_ids as JSON."""
    rows = ingest(text="Jefe de Compras\nJefe Compras\nIngeniero de Software")
    preview = create_preview_job(
        conn,
        text="\n".join(r[1] for r in rows),
        threshold=90,
        titles_per_request=25,
    )

    commit_job(conn, fake_anthropic, preview.job_id)

    # Get the batch
    batches = batches_dao.list_batches_for_job(conn, preview.job_id)
    batch = batches[0]

    # Get the request
    requests = batch_requests_dao.list_requests_for_batch(conn, batch.id)
    assert len(requests) == 1
    req = requests[0]

    # Verify cluster_ids is a list of integers
    assert isinstance(req.cluster_ids, list)
    assert all(isinstance(cid, int) for cid in req.cluster_ids)

    # Verify cluster IDs match what's in the database
    clusters = clusters_dao.list_clusters(conn, preview.job_id)
    cluster_ids_in_db = {c.id for c in clusters}
    cluster_ids_in_req = set(req.cluster_ids)
    assert cluster_ids_in_req == cluster_ids_in_db


def test_commit_handles_last_smaller_request(conn, fake_anthropic):
    """Verify that commit_job correctly handles the last request being smaller than titles_per_request."""
    # Create enough clusters to have multiple requests, with the last one being smaller
    rows = ingest(
        text="Jefe de Compras\nJefe Compras\n"
        "Ingeniero de Software\nIngeniero Software\n"
        "Gerente de Producto\nGerente Producto\n"
        "VP de Ventas\nVicepresidente de Ventas\n"
        "Director de Finanzas\nDirector Finanzas\n"
        "Contador General\nContador"
    )
    # titles_per_request=3 means we'll have 4 requests: 3, 3, 3, 2
    titles_per_request = 3
    preview = create_preview_job(
        conn,
        text="\n".join(r[1] for r in rows),
        threshold=85,  # Lower threshold to create fewer clusters
        titles_per_request=titles_per_request,
    )

    commit_job(conn, fake_anthropic, preview.job_id)

    # Get clusters
    clusters = clusters_dao.list_clusters(conn, preview.job_id)

    # Verify the last request was handled correctly
    batches = batches_dao.list_batches_for_job(conn, preview.job_id)
    batch = batches[0]
    requests = batch_requests_dao.list_requests_for_batch(conn, batch.id)

    # The sum of cluster_ids across all requests should equal total clusters
    all_cluster_ids = []
    for req in requests:
        all_cluster_ids.extend(req.cluster_ids)

    assert len(all_cluster_ids) == len(clusters)
    assert len(set(all_cluster_ids)) == len(clusters)  # All unique

    # Verify fake client received correctly-sized request params
    fake_batch = fake_anthropic.batches[batch.id]
    total_titles_sent = 0
    for req_params in fake_batch.requests:
        # Each request should have titles matching the actual cluster count for that request
        tool_schema = req_params["tools"][0]
        min_items = tool_schema["input_schema"]["properties"]["results"]["minItems"]
        max_items = tool_schema["input_schema"]["properties"]["results"]["maxItems"]
        titles_in_request = len(req_params["messages"][0]["content"].split('"title": ')) - 1
        assert min_items == max_items == titles_in_request
        total_titles_sent += titles_in_request

    assert total_titles_sent == len(clusters)
