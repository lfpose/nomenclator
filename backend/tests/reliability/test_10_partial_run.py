"""Test 10: Partial run row count matches subset.

This test verifies that a partial run (first_n=50 from a 500-row input)
produces a CSV with exactly 50 rows, all populated, and that the rows
are the first N from the original input.
"""
from app.anthropic.dry_run import generate_dry_run_results
from app.csv_io.parser import parse_csv
from app.csv_io.exporter import export_job_to_csv
from app.jobs.service import create_preview_job, commit_job, transition
from app.dao.batch_requests import list_requests_for_batch, mark_request_completed
from app.dao.batches import list_batches_for_job, update_batch_status
from app.dao.clusters import list_clusters, update_cluster_answers
from app.dao.spend_log import insert_spend


def _create_completed_job_with_subset(conn, fake_anthropic, total_rows=500, subset_n=50):
    """Create a completed job with row subset.

    Args:
        conn: Database connection
        fake_anthropic: Fake Anthropic client
        total_rows: Total number of input rows
        subset_n: Number of rows to select (first_n mode)

    Returns:
        job_id: The ID of the completed job
        input_titles: List of all input titles (for verification)
    """
    # Generate synthetic job titles
    titles = [f"Job Title {i}" for i in range(total_rows)]
    csv_data = "\n".join(titles).encode("utf-8")

    # Create preview job with row subset
    parse_csv(csv_data)
    result = create_preview_job(
        conn,
        file_bytes=csv_data,
        text=None,
        threshold=90,
        titles_per_request=25,
        row_subset_mode="first_n",
        row_subset_n=subset_n,
    )
    job_id = result.job_id

    # Verify the PreviewResult has correct counts
    assert result.total_input_rows == total_rows
    assert result.selected_rows == subset_n

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

    # Transition job to completed
    transition(conn, job_id, "polling", reason="test_poll")
    transition(conn, job_id, "completed", reason="test_completion")

    return job_id, titles


def test_partial_run_output_has_exactly_n_rows(conn, fake_anthropic):
    """Verify that partial run produces exactly N data rows in output CSV."""
    total_rows = 500
    subset_n = 50

    # Create completed job with row subset
    job_id, input_titles = _create_completed_job_with_subset(
        conn, fake_anthropic, total_rows=total_rows, subset_n=subset_n
    )

    # Export CSV
    csv_bytes = export_job_to_csv(conn, job_id)
    data_rows = csv_bytes.decode("utf-8-sig").splitlines()[1:]  # skip header

    # Assert output has exactly subset_n data rows
    assert len(data_rows) == subset_n, f"Expected {subset_n} rows, got {len(data_rows)}"


def test_partial_run_rows_are_first_n_from_input(conn, fake_anthropic):
    """Verify that partial run includes the first N rows from input."""
    total_rows = 500
    subset_n = 50

    # Create completed job with row subset
    job_id, input_titles = _create_completed_job_with_subset(
        conn, fake_anthropic, total_rows=total_rows, subset_n=subset_n
    )

    # Export CSV
    csv_bytes = export_job_to_csv(conn, job_id)
    lines = csv_bytes.decode("utf-8-sig").splitlines()

    # Skip header, get data rows
    data_rows = lines[1:]

    # Extract the 'original' column (first column) from each row
    output_originals = [row.split(",")[0] for row in data_rows]

    # Verify that output contains the first subset_n input titles
    expected_originals = input_titles[:subset_n]
    assert output_originals == expected_originals, (
        f"Output rows don't match first {subset_n} input rows. "
        f"Expected {expected_originals[:5]}..., got {output_originals[:5]}..."
    )


def test_partial_run_all_rows_populated(conn, fake_anthropic):
    """Verify that all rows in partial run output are populated."""
    total_rows = 500
    subset_n = 50

    # Create completed job with row subset
    job_id, input_titles = _create_completed_job_with_subset(
        conn, fake_anthropic, total_rows=total_rows, subset_n=subset_n
    )

    # Export CSV
    csv_bytes = export_job_to_csv(conn, job_id)
    lines = csv_bytes.decode("utf-8-sig").splitlines()

    # Skip header, get data rows
    data_rows = lines[1:]

    # Parse each CSV row and verify all answer columns are populated
    for row in data_rows:
        parts = row.split(",")
        # CSV format: original, male_es, female_es, category, error
        original, male_es, female_es, category, error = parts

        # All answer columns should be populated (not empty)
        # and error column should be empty (no errors)
        assert male_es, f"male_es is empty for row: {original}"
        assert female_es, f"female_es is empty for row: {original}"
        assert category, f"category is empty for row: {original}"
        assert error == "", f"error column is not empty for row: {original}"
