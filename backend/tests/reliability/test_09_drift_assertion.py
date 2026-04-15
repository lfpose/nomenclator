"""Test 9: Pre-write assertion fires on drift.

This test verifies that when row count drift is detected during export,
the download fails with 500, the job transitions to failed, and no CSV
bytes are returned (never a partial CSV).
"""
import sqlite3

from app.anthropic.dry_run import generate_dry_run_results
from app.csv_io.parser import parse_csv
from app.jobs.service import create_preview_job, commit_job, transition
from app.dao.batch_requests import list_requests_for_batch, mark_request_completed
from app.dao.batches import list_batches_for_job
from app.dao.clusters import list_clusters, update_cluster_answers
from app.dao.batches import update_batch_status
from app.dao.spend_log import insert_spend
from app.dao.jobs import get_job


def _create_completed_job_in_db(conn, fake_anthropic, n_rows=10):
    """Create a completed job in the given database connection.
    
    This is a simplified version of run_e2e that works with any connection.
    """
    # Generate synthetic job titles
    titles = [f"Job Title {i}" for i in range(n_rows)]
    csv_data = "\n".join(titles).encode("utf-8")

    # Create preview job
    parse_csv(csv_data)
    result = create_preview_job(
        conn,
        file_bytes=csv_data,
        text=None,
        threshold=90,
        titles_per_request=25,
    )
    job_id = result.job_id

    # Commit job
    commit_job(
        conn,
        fake_anthropic,
        job_id,
    )

    # Complete the batch with fake results
    batches = list_batches_for_job(conn, job_id)
    for batch in batches:
        requests = list_requests_for_batch(conn, batch.id)
        cluster_ids = []
        titles_for_results = []
        for req in requests:
            for cid in req.cluster_ids:
                cluster_ids.append(cid)
                # Get cluster representative
                clusters = list_clusters(conn, job_id)
                cluster = next((c for c in clusters if c.id == cid), None)
                if cluster:
                    titles_for_results.append(cluster.representative_original)

        if cluster_ids:
            # Generate fake results
            fake_result = generate_dry_run_results(cluster_ids, titles_for_results)

            # Mark requests as completed
            for i, req in enumerate(requests):
                mark_request_completed(
                    conn,
                    req.id,
                    raw_response=fake_result.model_dump_json(),
                )

            # Update batch status
            update_batch_status(conn, batch.id, "ended")

            # Write answers to clusters
            for i, cluster_id in enumerate(cluster_ids):
                update_cluster_answers(
                    conn,
                    cluster_id,
                    male_es=fake_result.results[i].male_es,
                    female_es=fake_result.results[i].female_es,
                    category=fake_result.results[i].category,
                )

            # Record spend
            import time
            insert_spend(
                conn,
                job_id=job_id,
                batch_id=batch.id,
                usd=0.0,
                at=int(time.time()),
            )

    # Transition job to completed (via polling for proper state machine)
    transition(conn, job_id, "polling", reason="test_poll")
    transition(conn, job_id, "completed", reason="test_completion")

    return job_id


def test_drift_assertion_fires_returns_500(logged_in_client, fake_anthropic):
    """Verify that row count drift causes download to return 500 with internal_error."""
    test_client, sid = logged_in_client

    # Get the database path from settings (set by logged_in_client fixture)
    from app.settings import settings
    db_path = settings.database_path

    # Create a direct connection to the same database
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row

    try:
        # Create a completed job with 10 rows
        job_id = _create_completed_job_in_db(conn, fake_anthropic, n_rows=10)

        # Corrupt the database by deleting a job_row directly
        conn.execute("DELETE FROM job_rows WHERE job_id = ? AND row_index = 5", (job_id,))

        # Attempt to download - should return 500 with internal_error
        r = test_client.get(f"/jobs/{job_id}/download", cookies={"sid": sid})
        assert r.status_code == 500
        assert r.json()["error"]["code"] == "internal_error"
    finally:
        conn.close()


def test_drift_transitions_job_to_failed(logged_in_client, fake_anthropic):
    """Verify that row count drift causes job to transition to failed state."""
    test_client, sid = logged_in_client

    # Get the database path from settings (set by logged_in_client fixture)
    from app.settings import settings
    db_path = settings.database_path

    # Create a direct connection to the same database
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row

    try:
        # Create a completed job with 10 rows
        job_id = _create_completed_job_in_db(conn, fake_anthropic, n_rows=10)

        # Verify job is initially completed
        job = get_job(conn, job_id)
        assert job.status == "completed"

        # Corrupt the database by deleting a job_row directly
        conn.execute("DELETE FROM job_rows WHERE job_id = ? AND row_index = 5", (job_id,))

        # Attempt to download - this should trigger the transition
        r = test_client.get(f"/jobs/{job_id}/download", cookies={"sid": sid})
        assert r.status_code == 500

        # Verify job is now in failed state
        job = get_job(conn, job_id)
        assert job.status == "failed"
    finally:
        conn.close()


def test_drift_never_returns_csv_bytes(logged_in_client, fake_anthropic):
    """Verify that row count drift never returns CSV bytes (always returns JSON error)."""
    test_client, sid = logged_in_client

    # Get the database path from settings (set by logged_in_client fixture)
    from app.settings import settings
    db_path = settings.database_path

    # Create a direct connection to the same database
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row

    try:
        # Create a completed job with 10 rows
        job_id = _create_completed_job_in_db(conn, fake_anthropic, n_rows=10)

        # Corrupt the database by deleting a job_row directly
        conn.execute("DELETE FROM job_rows WHERE job_id = ? AND row_index = 5", (job_id,))

        # Attempt to download - should return JSON error, not CSV
        r = test_client.get(f"/jobs/{job_id}/download", cookies={"sid": sid})
        assert r.status_code == 500

        # Verify response is JSON, not CSV
        assert "application/json" in r.headers.get("content-type", "")
        assert r.json()["error"]["code"] == "internal_error"

        # Verify no CSV content is returned
        # The response should be JSON with error envelope, not CSV bytes
        assert "error" in r.json()
        assert "original" not in r.json()  # No CSV header row
    finally:
        conn.close()

