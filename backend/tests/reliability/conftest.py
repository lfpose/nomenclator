import pytest

from app.anthropic.dry_run import generate_dry_run_results
from app.jobs.service import commit_job


@pytest.fixture
def run_e2e():
    """Helper fixture that runs a full E2E test scenario.

    Creates a preview job with n_rows synthetic job titles, commits it,
    completes the fake batch with synthetic answers using FakeAnthropicBatchClient,
    and returns the job_id.

    Args:
        conn: Database connection (from fixture)
        fake: FakeAnthropicBatchClient (from fixture)
        n_rows: Number of rows to generate
        conn: Database connection

    Returns:
        job_id: The ID of the completed job
    """

    def _run(n_rows, conn, fake):
        # Generate synthetic Spanish job titles
        titles = [f"Job Title {i}" for i in range(n_rows)]
        csv_data = "\n".join(titles).encode("utf-8")

        # Create preview job
        from app.csv_io.parser import parse_csv
        from app.jobs.service import create_preview_job

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
            fake,
            job_id,
        )

        # Complete the batch with fake results
        from app.dao.batch_requests import list_requests_for_batch

        # Get all batches for the job
        from app.dao.batches import list_batches_for_job

        batches = list_batches_for_job(conn, job_id)
        for batch in batches:
            requests = list_requests_for_batch(conn, batch.id)
            cluster_ids = []
            titles = []
            for req in requests:
                for cid in req.cluster_ids:
                    cluster_ids.append(cid)
                    # Get cluster representative
                    from app.dao.clusters import list_clusters

                    clusters = list_clusters(conn, job_id)
                    cluster = next((c for c in clusters if c.id == cid), None)
                    if cluster:
                        titles.append(cluster.representative_original)

            if cluster_ids:
                # Generate fake results
                fake_result = generate_dry_run_results(cluster_ids, titles)

                # Mark requests as completed
                for i, req in enumerate(requests):
                    from app.dao.batch_requests import mark_request_completed

                    mark_request_completed(
                        conn,
                        req.id,
                        raw_response=fake_result.model_dump_json(),
                    )

                # Update batch status
                from app.dao.batches import update_batch_status

                update_batch_status(conn, batch.id, "ended")

                # Write answers to clusters
                for i, cluster_id in enumerate(cluster_ids):
                    from app.dao.clusters import update_cluster_answers

                    update_cluster_answers(
                        conn,
                        cluster_id,
                        male_es=fake_result.results[i].male_es,
                        female_es=fake_result.results[i].female_es,
                        category=fake_result.results[i].category,
                    )

                # Record spend
                from app.dao.spend_log import insert_spend
                import time

                insert_spend(
                    conn,
                    job_id=job_id,
                    batch_id=batch.id,
                    usd=0.0,
                    at=int(time.time()),
                )

        # Transition job to completed (via polling for proper state machine)
        from app.jobs.service import transition

        # Transition submitted -> polling (simulating worker poll)
        transition(conn, job_id, "polling", reason="test_poll")

        # Transition polling -> completed
        transition(conn, job_id, "completed", reason="test_completion")

        return job_id

    return _run
