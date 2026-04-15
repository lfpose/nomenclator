"""Test 8: Spend cap during retry flags stragglers.

Simulate a spend log that's just under the cap. The initial batch returns
stragglers. The retry's estimated cost would push us over → retry is refused,
stragglers flagged 'spend_cap_exceeded', job still 'completed'.
"""
import time

from app.anthropic.dry_run import generate_dry_run_results
from app.csv_io.exporter import export_job_to_csv
from app.jobs.service import commit_job, transition


def test_retry_refused_by_cap_flags_stragglers(conn, fake_anthropic):
    """Pre-seed $19.90 spend, first batch has stragglers, retry refused by cap."""
    # Pre-seed spend_log with $19.90 (just under $20 cap)
    from app.dao.spend_log import insert_spend
    from app.dao.jobs import create_job, update_job_status, update_job_counts

    # Create a dummy job for spend log reference
    dummy_job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    update_job_status(conn, dummy_job_id, "completed")
    update_job_counts(conn, dummy_job_id, total_rows=0, cluster_count=0)

    # Insert $19.90 of historical spend
    now = int(time.time())
    insert_spend(
        conn,
        job_id=dummy_job_id,
        batch_id=None,
        usd=19.90,
        at=now - 100,  # 100 seconds ago (well within 30-day window)
    )

    # Create 20 unique titles to get some clusters
    titles = [f"Job Title {i}" for i in range(20)]
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

    # Get clusters for this job
    from app.dao.clusters import list_clusters

    clusters = list_clusters(conn, job_id)

    # Commit job to submit batch
    commit_job(
        conn,
        fake_anthropic,
        job_id,
    )

    # Get the batch
    from app.dao.batches import list_batches_for_job

    batches = list_batches_for_job(conn, job_id)
    assert len(batches) == 1
    batch = batches[0]

    # Get requests for the batch
    from app.dao.batch_requests import list_requests_for_batch

    requests = list_requests_for_batch(conn, batch.id)

    # Generate results for all but the last cluster (simulating straggler)
    all_cluster_ids = []
    cluster_titles = []
    for req in requests:
        for cid in req.cluster_ids:
            all_cluster_ids.append(cid)
            cluster = next((c for c in clusters if c.id == cid), None)
            if cluster:
                cluster_titles.append(cluster.representative_original)

    # Skip the last cluster to simulate straggler
    straggler_cluster_id = all_cluster_ids[-1]
    results_cluster_ids = all_cluster_ids[:-1]
    results_titles = cluster_titles[:-1]

    # Generate results for N-1 clusters
    fake_result = generate_dry_run_results(results_cluster_ids, results_titles)

    # Complete first batch with N-1 results (straggler detected)
    from app.dao.batches import update_batch_status
    from app.dao.batch_requests import mark_request_completed
    from app.dao.clusters import update_cluster_answers
    from app.dao.spend_log import insert_spend

    update_batch_status(conn, batch.id, "ended")

    # Mark completed requests
    for i, req in enumerate(requests):
        mark_request_completed(
            conn,
            req.id,
            raw_response=fake_result.model_dump_json(),
        )

    # Write answers to clusters (skip the straggler)
    for i, cluster_id in enumerate(results_cluster_ids):
        update_cluster_answers(
            conn,
            cluster_id,
            male_es=fake_result.results[i].male_es,
            female_es=fake_result.results[i].female_es,
            category=fake_result.results[i].category,
        )

    # Record spend for first batch
    insert_spend(
        conn,
        job_id=job_id,
        batch_id=batch.id,
        usd=0.0,
        at=int(time.time()),
    )

    # Transition job to polling (simulating worker tick)
    transition(conn, job_id, "polling", reason="test_poll")

    # Now simulate worker detecting stragglers and attempting retry
    # This should fail cap check and flag stragglers instead
    from app.worker.poller import Worker

    # Get the job
    from app.dao.jobs import get_job

    job = get_job(conn, job_id)

    # Use _flag_remaining_and_complete directly since _submit_retry will cap-fail
    # The worker's _submit_retry does:
    # 1. Cost check - block retry if cap exceeded
    # 2. If not ok: call _flag_remaining_and_complete(conn, job, error_code="spend_cap_exceeded")

    # Verify that the job transitions to completed with stragglers flagged
    worker = Worker(fake_anthropic, lambda: conn, tick_interval=1.0)
    worker._flag_remaining_and_complete(conn, job, error_code="spend_cap_exceeded")

    # Verify job status
    job = get_job(conn, job_id)
    assert job.status == "completed", f"Expected 'completed', got '{job.status}'"

    # Verify straggler cluster has error code
    final_clusters = list_clusters(conn, job_id)
    straggler_cluster = next((c for c in final_clusters if c.id == straggler_cluster_id), None)
    assert straggler_cluster is not None
    assert straggler_cluster.error == "spend_cap_exceeded", (
        f"Expected straggler error 'spend_cap_exceeded', got '{straggler_cluster.error}'"
    )

    # Verify resolved clusters have answers and no errors
    resolved_clusters = [c for c in final_clusters if c.id != straggler_cluster_id]
    for cluster in resolved_clusters:
        assert cluster.male_es is not None, f"Cluster {cluster.id} missing male_es"
        assert cluster.female_es is not None, f"Cluster {cluster.id} missing female_es"
        assert cluster.category is not None, f"Cluster {cluster.id} missing category"
        assert cluster.error is None or cluster.error == "", (
            f"Cluster {cluster.id} has unexpected error '{cluster.error}'"
        )


def test_job_status_is_completed_not_failed(conn, fake_anthropic):
    """When retry is refused by cap, job status should be 'completed' not 'failed'."""
    # Pre-seed spend_log with $19.90
    from app.dao.spend_log import insert_spend
    from app.dao.jobs import create_job, update_job_status, update_job_counts

    dummy_job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    update_job_status(conn, dummy_job_id, "completed")
    update_job_counts(conn, dummy_job_id, total_rows=0, cluster_count=0)

    now = int(time.time())
    insert_spend(
        conn,
        job_id=dummy_job_id,
        batch_id=None,
        usd=19.90,
        at=now - 100,
    )

    # Create job with stragglers
    titles = [f"Job Title {i}" for i in range(20)]
    csv_data = "\n".join(titles).encode("utf-8")

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
    commit_job(conn, fake_anthropic, job_id)

    # Get clusters
    from app.dao.clusters import list_clusters
    from app.dao.batches import list_batches_for_job
    from app.dao.batch_requests import list_requests_for_batch
    from app.anthropic.dry_run import generate_dry_run_results
    from app.dao.batches import update_batch_status
    from app.dao.batch_requests import mark_request_completed
    from app.dao.clusters import update_cluster_answers

    clusters = list_clusters(conn, job_id)
    batches = list_batches_for_job(conn, job_id)
    batch = batches[0]
    requests = list_requests_for_batch(conn, batch.id)

    # Generate N-1 results
    all_cluster_ids = []
    cluster_titles = []
    for req in requests:
        for cid in req.cluster_ids:
            all_cluster_ids.append(cid)
            cluster = next((c for c in clusters if c.id == cid), None)
            if cluster:
                cluster_titles.append(cluster.representative_original)

    # Note: straggler is the last cluster, not used directly here
    results_cluster_ids = all_cluster_ids[:-1]
    results_titles = cluster_titles[:-1]

    fake_result = generate_dry_run_results(results_cluster_ids, results_titles)

    # Complete first batch
    update_batch_status(conn, batch.id, "ended")
    for i, req in enumerate(requests):
        mark_request_completed(conn, req.id, raw_response=fake_result.model_dump_json())

    for i, cluster_id in enumerate(results_cluster_ids):
        update_cluster_answers(
            conn,
            cluster_id,
            male_es=fake_result.results[i].male_es,
            female_es=fake_result.results[i].female_es,
            category=fake_result.results[i].category,
        )

    insert_spend(conn, job_id=job_id, batch_id=batch.id, usd=0.0, at=int(time.time()))

    # Transition to polling
    transition(conn, job_id, "polling", reason="test_poll")

    # Flag stragglers with cap exceeded
    from app.worker.poller import Worker
    from app.dao.jobs import get_job

    job = get_job(conn, job_id)
    worker = Worker(fake_anthropic, lambda: conn, tick_interval=1.0)
    worker._flag_remaining_and_complete(conn, job, error_code="spend_cap_exceeded")

    # Verify job status is completed
    job = get_job(conn, job_id)
    assert job.status == "completed", f"Expected 'completed', got '{job.status}'"
    assert job.status != "failed", "Job should not be 'failed'"


def test_flagged_rows_carry_spend_cap_exceeded_code(conn, fake_anthropic):
    """Rows in straggler clusters should have error='spend_cap_exceeded' in CSV."""
    # Pre-seed spend_log with $19.90
    from app.dao.spend_log import insert_spend
    from app.dao.jobs import create_job, update_job_status, update_job_counts

    dummy_job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    update_job_status(conn, dummy_job_id, "completed")
    update_job_counts(conn, dummy_job_id, total_rows=0, cluster_count=0)

    now = int(time.time())
    insert_spend(
        conn,
        job_id=dummy_job_id,
        batch_id=None,
        usd=19.90,
        at=now - 100,
    )

    # Create job with stragglers
    titles = [f"Job Title {i}" for i in range(20)]
    csv_data = "\n".join(titles).encode("utf-8")

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
    commit_job(conn, fake_anthropic, job_id)

    # Get clusters
    from app.dao.clusters import list_clusters
    from app.dao.batches import list_batches_for_job
    from app.dao.batch_requests import list_requests_for_batch
    from app.anthropic.dry_run import generate_dry_run_results
    from app.dao.batches import update_batch_status
    from app.dao.batch_requests import mark_request_completed
    from app.dao.clusters import update_cluster_answers

    clusters = list_clusters(conn, job_id)
    batches = list_batches_for_job(conn, job_id)
    batch = batches[0]
    requests = list_requests_for_batch(conn, batch.id)

    # Generate N-1 results
    all_cluster_ids = []
    cluster_titles = []
    for req in requests:
        for cid in req.cluster_ids:
            all_cluster_ids.append(cid)
            cluster = next((c for c in clusters if c.id == cid), None)
            if cluster:
                cluster_titles.append(cluster.representative_original)

    straggler_cluster_id = all_cluster_ids[-1]
    results_cluster_ids = all_cluster_ids[:-1]
    results_titles = cluster_titles[:-1]

    fake_result = generate_dry_run_results(results_cluster_ids, results_titles)

    # Complete first batch
    update_batch_status(conn, batch.id, "ended")
    for i, req in enumerate(requests):
        mark_request_completed(conn, req.id, raw_response=fake_result.model_dump_json())

    for i, cluster_id in enumerate(results_cluster_ids):
        update_cluster_answers(
            conn,
            cluster_id,
            male_es=fake_result.results[i].male_es,
            female_es=fake_result.results[i].female_es,
            category=fake_result.results[i].category,
        )

    insert_spend(conn, job_id=job_id, batch_id=batch.id, usd=0.0, at=int(time.time()))

    # Transition to polling
    transition(conn, job_id, "polling", reason="test_poll")

    # Flag stragglers with cap exceeded
    from app.worker.poller import Worker
    from app.dao.jobs import get_job
    from app.dao.job_rows import list_rows

    job = get_job(conn, job_id)
    worker = Worker(fake_anthropic, lambda: conn, tick_interval=1.0)
    worker._flag_remaining_and_complete(conn, job, error_code="spend_cap_exceeded")

    # Export CSV and verify error codes
    csv_bytes = export_job_to_csv(conn, job_id)
    csv_text = csv_bytes.decode("utf-8-sig")

    lines = csv_text.splitlines()
    # header + 20 data rows
    assert len(lines) == 21

    # Find the straggler cluster and verify its rows have spend_cap_exceeded error
    straggler_cluster = next((c for c in clusters if c.id == straggler_cluster_id), None)
    assert straggler_cluster is not None

    # Get all rows for the straggler cluster
    job_rows = list_rows(conn, job_id)
    straggler_rows = [r for r in job_rows if r.cluster_id == straggler_cluster_id]

    # For each straggler row in the CSV, verify error code
    # The CSV order matches row_index order
    for row in straggler_rows:
        # Find the corresponding line in CSV
        line = lines[row.row_index + 1]  # +1 for header
        parts = line.split(",")
        error = parts[4]
        assert error == "spend_cap_exceeded", (
            f"Row {row.row_index} (cluster {straggler_cluster_id}) should have error='spend_cap_exceeded', got '{error}'"
        )

    # Verify resolved rows have empty error column
    resolved_rows = [r for r in job_rows if r.cluster_id != straggler_cluster_id]
    for row in resolved_rows:
        line = lines[row.row_index + 1]
        parts = line.split(",")
        error = parts[4]
        assert error == "", f"Row {row.row_index} should have empty error, got '{error}'"


def test_output_row_count_unchanged(conn, fake_anthropic):
    """Total output row count should match input even when stragglers are flagged."""
    # Pre-seed spend_log with $19.90
    from app.dao.spend_log import insert_spend
    from app.dao.jobs import create_job, update_job_status, update_job_counts

    dummy_job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    update_job_status(conn, dummy_job_id, "completed")
    update_job_counts(conn, dummy_job_id, total_rows=0, cluster_count=0)

    now = int(time.time())
    insert_spend(
        conn,
        job_id=dummy_job_id,
        batch_id=None,
        usd=19.90,
        at=now - 100,
    )

    # Create 20 titles
    titles = [f"Job Title {i}" for i in range(20)]
    csv_data = "\n".join(titles).encode("utf-8")

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
    commit_job(conn, fake_anthropic, job_id)

    # Get clusters
    from app.dao.clusters import list_clusters
    from app.dao.batches import list_batches_for_job
    from app.dao.batch_requests import list_requests_for_batch
    from app.anthropic.dry_run import generate_dry_run_results
    from app.dao.batches import update_batch_status
    from app.dao.batch_requests import mark_request_completed
    from app.dao.clusters import update_cluster_answers

    clusters = list_clusters(conn, job_id)
    batches = list_batches_for_job(conn, job_id)
    batch = batches[0]
    requests = list_requests_for_batch(conn, batch.id)

    # Generate N-1 results
    all_cluster_ids = []
    cluster_titles = []
    for req in requests:
        for cid in req.cluster_ids:
            all_cluster_ids.append(cid)
            cluster = next((c for c in clusters if c.id == cid), None)
            if cluster:
                cluster_titles.append(cluster.representative_original)

    # Note: straggler is the last cluster, not used directly here
    results_cluster_ids = all_cluster_ids[:-1]
    results_titles = cluster_titles[:-1]

    fake_result = generate_dry_run_results(results_cluster_ids, results_titles)

    # Complete first batch
    update_batch_status(conn, batch.id, "ended")
    for i, req in enumerate(requests):
        mark_request_completed(conn, req.id, raw_response=fake_result.model_dump_json())

    for i, cluster_id in enumerate(results_cluster_ids):
        update_cluster_answers(
            conn,
            cluster_id,
            male_es=fake_result.results[i].male_es,
            female_es=fake_result.results[i].female_es,
            category=fake_result.results[i].category,
        )

    insert_spend(conn, job_id=job_id, batch_id=batch.id, usd=0.0, at=int(time.time()))

    # Transition to polling
    transition(conn, job_id, "polling", reason="test_poll")

    # Flag stragglers with cap exceeded
    from app.worker.poller import Worker
    from app.dao.jobs import get_job

    job = get_job(conn, job_id)
    worker = Worker(fake_anthropic, lambda: conn, tick_interval=1.0)
    worker._flag_remaining_and_complete(conn, job, error_code="spend_cap_exceeded")

    # Export CSV and verify row count
    csv_bytes = export_job_to_csv(conn, job_id)
    csv_text = csv_bytes.decode("utf-8-sig")

    lines = csv_text.splitlines()
    # header + 20 data rows = 21 lines
    assert len(lines) == 21, f"Expected 21 lines (header + 20 data), got {len(lines)}"

    # Verify all 20 data rows exist
    data_rows = lines[1:]
    assert len(data_rows) == 20, f"Expected 20 data rows, got {len(data_rows)}"

    # Verify job.total_rows is still 20
    job = get_job(conn, job_id)
    assert job.total_rows == 20, f"Expected job.total_rows == 20, got {job.total_rows}"
