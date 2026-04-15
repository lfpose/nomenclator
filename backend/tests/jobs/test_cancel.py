"""Tests for cancel_job function in jobs/service.py."""

import pytest

from app.dao import batches as batches_dao
from app.dao import jobs as jobs_dao
from app.jobs.service import cancel_job, commit_job, create_preview_job
from app.csv_io.ingest import ingest


def test_cancel_transitions_to_cancelled(conn, fake_anthropic):
    """Verify that cancel_job transitions job to cancelled state."""
    # Create and commit a job to get it to submitted state
    rows = ingest(text="Jefe de Compras\nJefe Compras")
    preview = create_preview_job(
        conn,
        text="\n".join(r[1] for r in rows),
        threshold=90,
        titles_per_request=25,
    )
    commit_job(conn, fake_anthropic, preview.job_id)

    # Cancel the job
    cancel_job(conn, fake_anthropic, preview.job_id)

    # Verify job is in cancelled state
    job = jobs_dao.get_job(conn, preview.job_id)
    assert job is not None
    assert job.status == "cancelled"


def test_cancel_calls_anthropic_cancel_for_inflight_batches(conn, fake_anthropic):
    """Verify that cancel_job calls Anthropic cancel for inflight batches."""
    # Create and commit a job
    rows = ingest(text="Jefe de Compras\nJefe Compras\nIngeniero de Software")
    preview = create_preview_job(
        conn,
        text="\n".join(r[1] for r in rows),
        threshold=90,
        titles_per_request=2,  # Creates multiple batches
    )
    commit_job(conn, fake_anthropic, preview.job_id)

    # Get the batch ID before cancellation
    batches = batches_dao.list_batches_for_job(conn, preview.job_id)
    batch_id = batches[0].id

    # Cancel the job
    cancel_job(conn, fake_anthropic, preview.job_id)

    # Verify Anthropic cancel was called
    fake_batch = fake_anthropic.batches[batch_id]
    assert fake_batch.processing_status == "canceled"


def test_cancel_ignores_already_ended_batches(conn, fake_anthropic):
    """Verify that cancel_job ignores already ended batches."""
    # Create and commit a job
    rows = ingest(text="Jefe de Compras\nJefe Compras")
    preview = create_preview_job(
        conn,
        text="\n".join(r[1] for r in rows),
        threshold=90,
        titles_per_request=25,
    )
    commit_job(conn, fake_anthropic, preview.job_id)

    # Mark batch as ended
    batches = batches_dao.list_batches_for_job(conn, preview.job_id)
    batch_id = batches[0].id
    batches_dao.update_batch_status(conn, batch_id, "ended")

    # Complete the fake batch
    fake_anthropic.complete_batch(batch_id, [])

    # Cancel the job - should not raise, just transition
    cancel_job(conn, fake_anthropic, preview.job_id)

    # Verify job is cancelled
    job = jobs_dao.get_job(conn, preview.job_id)
    assert job.status == "cancelled"


def test_cancel_raises_on_terminal_state(conn, fake_anthropic):
    """Verify that cancel_job raises ValueError for terminal states."""
    # Create and commit a job
    rows = ingest(text="Jefe de Compras\nJefe Compras")
    preview = create_preview_job(
        conn,
        text="\n".join(r[1] for r in rows),
        threshold=90,
        titles_per_request=25,
    )
    commit_job(conn, fake_anthropic, preview.job_id)

    # Cancel to get to cancelled state
    cancel_job(conn, fake_anthropic, preview.job_id)

    # Try to cancel again - should raise
    with pytest.raises(ValueError, match="invalid_state"):
        cancel_job(conn, fake_anthropic, preview.job_id)


def test_cancel_swallows_anthropic_cancel_errors(conn, fake_anthropic):
    """Verify that cancel_job swallows errors from Anthropic cancel."""
    # Create and commit a job
    rows = ingest(text="Jefe de Compras\nJefe Compras")
    preview = create_preview_job(
        conn,
        text="\n".join(r[1] for r in rows),
        threshold=90,
        titles_per_request=25,
    )
    commit_job(conn, fake_anthropic, preview.job_id)

    # Make the fake client raise an error on cancel
    original_cancel = fake_anthropic.cancel_batch

    def raise_error(batch_id):
        raise RuntimeError("Anthropic API error")

    fake_anthropic.cancel_batch = raise_error

    # Cancel should not raise - it should swallow the error
    cancel_job(conn, fake_anthropic, preview.job_id)

    # Verify job is cancelled despite the Anthropic error
    job = jobs_dao.get_job(conn, preview.job_id)
    assert job.status == "cancelled"

    # Restore the original cancel function
    fake_anthropic.cancel_batch = original_cancel
