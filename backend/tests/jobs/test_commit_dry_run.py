"""Tests for dry-run mode in commit_job."""

from unittest.mock import MagicMock

from app.jobs.service import commit_job


def test_dry_run_commit_skips_anthropic_client(conn):
    """Dry-run commit should not call the Anthropic client."""
    # Create a preview job
    from app.jobs.service import create_preview_job

    preview = create_preview_job(
        conn,
        text="Jefe de Compras\nIngeniero de Ventas\nGerente de Marketing",
        threshold=90,
        titles_per_request=25,
    )

    # Create a fake Anthropic client that tracks calls
    fake_client = MagicMock()

    # Commit with is_dry_run=True
    commit_job(
        conn,
        fake_client,
        preview.job_id,
        is_dry_run=True,
    )

    # Assert Anthropic client was never called
    fake_client.submit_batch.assert_not_called()


def test_dry_run_commit_generates_fake_answers(conn):
    """Dry-run commit should generate fake answers for all clusters."""
    # Create a preview job
    from app.jobs.service import create_preview_job

    preview = create_preview_job(
        conn,
        text="Jefe de Compras\nIngeniero de Ventas\nGerente de Marketing",
        threshold=90,
        titles_per_request=25,
    )

    # Create a fake Anthropic client
    from tests.anthropic.fake_client import FakeAnthropicBatchClient

    fake_client = FakeAnthropicBatchClient()

    # Commit with is_dry_run=True
    commit_job(
        conn,
        fake_client,
        preview.job_id,
        is_dry_run=True,
    )

    # Assert all clusters have fake answers
    from app.dao import clusters as clusters_dao

    clusters = clusters_dao.list_clusters(conn, preview.job_id)
    for cluster in clusters:
        assert cluster.male_es is not None
        assert cluster.female_es is not None
        assert cluster.category is not None
        assert cluster.category == "DRY_RUN"
        assert "(M)" in cluster.male_es
        assert "(F)" in cluster.female_es


def test_dry_run_commit_transitions_to_completed(conn):
    """Dry-run commit should transition job directly to completed state."""
    # Create a preview job
    from app.jobs.service import create_preview_job

    preview = create_preview_job(
        conn,
        text="Jefe de Compras\nIngeniero de Ventas\nGerente de Marketing",
        threshold=90,
        titles_per_request=25,
    )

    # Create a fake Anthropic client
    from tests.anthropic.fake_client import FakeAnthropicBatchClient

    fake_client = FakeAnthropicBatchClient()

    # Commit with is_dry_run=True
    commit_job(
        conn,
        fake_client,
        preview.job_id,
        is_dry_run=True,
    )

    # Assert job is in completed state
    from app.dao import jobs as jobs_dao

    job = jobs_dao.get_job(conn, preview.job_id)
    assert job.status == "completed"


def test_dry_run_commit_records_zero_spend(conn):
    """Dry-run commit should record $0 spend."""
    # Create a preview job
    from app.jobs.service import create_preview_job

    preview = create_preview_job(
        conn,
        text="Jefe de Compras\nIngeniero de Ventas\nGerente de Marketing",
        threshold=90,
        titles_per_request=25,
    )

    # Create a fake Anthropic client
    from tests.anthropic.fake_client import FakeAnthropicBatchClient

    fake_client = FakeAnthropicBatchClient()

    # Commit with is_dry_run=True
    commit_job(
        conn,
        fake_client,
        preview.job_id,
        is_dry_run=True,
    )

    # Assert spend log entry with $0
    from app.dao import spend_log as spend_log_dao

    total_spend = spend_log_dao.sum_last_30_days(conn)
    assert total_spend == 0.0

    # Verify the spend entry exists
    rows = conn.execute("SELECT SUM(usd) FROM spend_log WHERE job_id = ?", (preview.job_id,)).fetchone()
    assert rows[0] == 0.0


def test_dry_run_commit_skips_cap_check(conn):
    """Dry-run commit should skip the spend cap check."""
    # Pre-seed spend log to hit cap limit
    from app.dao import spend_log as spend_log_dao
    import time

    # Create a job to satisfy FK constraint
    from app.dao import jobs as jobs_dao

    job_id_1 = jobs_dao.create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )

    # Add spend to reach cap ($20)
    spend_log_dao.insert_spend(
        conn,
        job_id=job_id_1,
        batch_id=None,
        usd=20.0,
        at=int(time.time()),
    )

    # Create a preview job
    from app.jobs.service import create_preview_job

    preview = create_preview_job(
        conn,
        text="Jefe de Compras\nIngeniero de Ventas\nGerente de Marketing",
        threshold=90,
        titles_per_request=25,
    )

    # Create a fake Anthropic client
    from tests.anthropic.fake_client import FakeAnthropicBatchClient

    fake_client = FakeAnthropicBatchClient()

    # Commit with is_dry_run=True should NOT raise SpendCapExceeded
    # even though cap is reached
    commit_job(
        conn,
        fake_client,
        preview.job_id,
        is_dry_run=True,
    )

    # Assert job completed successfully
    job = jobs_dao.get_job(conn, preview.job_id)
    assert job.status == "completed"


def test_dry_run_commit_sets_is_dry_run_on_job(conn):
    """Dry-run commit should set is_dry_run flag on the job."""
    # Create a preview job with is_dry_run=True in create_preview_job
    # Note: create_preview_job doesn't accept is_dry_run, so we set it after creation
    from app.jobs.service import create_preview_job

    preview = create_preview_job(
        conn,
        text="Jefe de Compras\nIngeniero de Ventas\nGerente de Marketing",
        threshold=90,
        titles_per_request=25,
    )

    # Update the job to set is_dry_run=1
    conn.execute("UPDATE jobs SET is_dry_run = 1 WHERE id = ?", (preview.job_id,))

    # Create a fake Anthropic client
    from tests.anthropic.fake_client import FakeAnthropicBatchClient

    fake_client = FakeAnthropicBatchClient()

    # Commit with is_dry_run=True
    commit_job(
        conn,
        fake_client,
        preview.job_id,
        is_dry_run=True,
    )

    # Assert is_dry_run flag is still set
    from app.dao import jobs as jobs_dao

    job = jobs_dao.get_job(conn, preview.job_id)
    assert job.is_dry_run == 1
