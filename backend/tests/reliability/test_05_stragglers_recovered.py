import json
import secrets
import time

from app.anthropic.dry_run import generate_dry_run_results
from app.csv_io.exporter import export_job_to_csv
from app.jobs.service import commit_job, transition


def test_stragglers_recovered_final_csv_all_populated(
    conn, fake_anthropic
):
    """Mock Anthropic to return N-1 results on first batch, all results on retry. Final CSV is fully populated."""
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
    # Get cluster representatives
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
    # Update batch status
    from app.dao.batches import update_batch_status

    update_batch_status(conn, batch.id, "ended")

    # Mark completed requests
    for i, req in enumerate(requests):
        from app.dao.batch_requests import mark_request_completed

        mark_request_completed(
            conn,
            req.id,
            raw_response=fake_result.model_dump_json(),
        )

    # Write answers to clusters (skip the straggler)
    from app.dao.clusters import update_cluster_answers
    for i, cluster_id in enumerate(results_cluster_ids):
        update_cluster_answers(
            conn,
            cluster_id,
            male_es=fake_result.results[i].male_es,
            female_es=fake_result.results[i].female_es,
            category=fake_result.results[i].category,
        )

    # Record spend for first batch
    from app.dao.spend_log import insert_spend
    import time

    insert_spend(
        conn,
        job_id=job_id,
        batch_id=batch.id,
        usd=0.0,
        at=int(time.time()),
    )

    # Transition job to polling (simulating worker tick)
    transition(conn, job_id, "polling", reason="test_poll")

    # Now simulate worker detecting stragglers and submitting retry
    # Submit retry batch with only the straggler
    retry_cluster_ids = [straggler_cluster_id]
    retry_titles = [cluster_titles[-1]]

    # Build retry batch request
    from app.anthropic.request_builder import build_request_params, build_system_prompt, TitleInput

    template = conn.execute(
        "SELECT system_prompt, few_shots FROM task_templates WHERE id = ?",
        ("job_titles_es",),
    ).fetchone()
    few_shots = json.loads(template["few_shots"])
    system_prompt = build_system_prompt(template["system_prompt"], few_shots)

    # Create TitleInput objects
    title_inputs = [TitleInput(id="t001", title=retry_titles[0])]

    params = build_request_params(
        titles=title_inputs,
        system_prompt=system_prompt,
        taxonomy=None,
        titles_per_request=1,
    )

    # Submit retry batch
    retry_batch_id = fake_anthropic.submit_batch(params)

    # Insert retry batch
    from app.dao.batches import insert_batch

    insert_batch(
        conn,
        id=retry_batch_id,
        job_id=job_id,
        retry_round=1,
        parent_batch_id=batch.id,
        status="in_progress",
        request_count=1,
    )

    # Insert retry request
    from app.dao.batch_requests import insert_request

    request_id = secrets.token_hex(16)
    insert_request(
        conn,
        id=request_id,
        batch_id=list_batches_for_job(conn, job_id)[-1].id,
        cluster_ids=[straggler_cluster_id],
    )

    # Get retry batch and request
    retry_batches = list_batches_for_job(conn, job_id)
    retry_batch = retry_batches[-1]
    retry_requests = list_requests_for_batch(conn, retry_batch.id)

    # Generate result for the straggler
    straggler_result = generate_dry_run_results(retry_cluster_ids, retry_titles)

    # Complete retry batch
    update_batch_status(conn, retry_batch.id, "ended")
    mark_request_completed(
        conn,
        retry_requests[0].id,
        raw_response=straggler_result.model_dump_json(),
    )

    # Write answer to straggler cluster
    update_cluster_answers(
        conn,
        straggler_cluster_id,
        male_es=straggler_result.results[0].male_es,
        female_es=straggler_result.results[0].female_es,
        category=straggler_result.results[0].category,
    )

    # Record spend for retry batch
    insert_spend(
        conn,
        job_id=job_id,
        batch_id=retry_batch.id,
        usd=0.0,
        at=int(time.time()),
    )

    # Transition job to completed
    transition(conn, job_id, "completed", reason="test_completion")

    # Export CSV and verify all rows are populated
    csv_bytes = export_job_to_csv(conn, job_id)
    csv_text = csv_bytes.decode("utf-8-sig")

    # Parse CSV
    lines = csv_text.splitlines()
    assert len(lines) == 21  # header + 20 data rows

    # Verify all data rows have non-empty answer columns
    for line in lines[1:]:  # Skip header
        # CSV format: original,male_es,female_es,category,error
        parts = line.split(",")
        male_es = parts[1]
        female_es = parts[2]
        category = parts[3]
        error = parts[4]

        assert male_es != "", f"male_es should not be empty: {line}"
        assert female_es != "", f"female_es should not be empty: {line}"
        assert category != "", f"category should not be empty: {line}"
        assert error == "", f"error should be empty but got '{error}': {line}"


def test_stragglers_recovery_produces_two_batches(conn, fake_anthropic):
    """Straggler recovery results in exactly 2 batch records (original + retry)."""
    # Create 20 unique titles
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

    # Get clusters
    from app.dao.clusters import list_clusters

    clusters = list_clusters(conn, job_id)

    # Commit job
    commit_job(conn, fake_anthropic, job_id)

    # Get batch and requests
    from app.dao.batches import list_batches_for_job
    from app.dao.batch_requests import list_requests_for_batch

    batches = list_batches_for_job(conn, job_id)
    batch = batches[0]
    requests = list_requests_for_batch(conn, batch.id)

    # Generate results for all but last cluster
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

    # Complete first batch with N-1 results
    from app.dao.batches import update_batch_status
    from app.dao.batch_requests import mark_request_completed
    from app.dao.clusters import update_cluster_answers
    from app.dao.spend_log import insert_spend

    fake_result = generate_dry_run_results(results_cluster_ids, results_titles)
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

    # Submit retry batch
    retry_cluster_ids = [straggler_cluster_id]
    retry_titles = [cluster_titles[-1]]

    from app.anthropic.request_builder import build_request_params, build_system_prompt, TitleInput

    template = conn.execute(
        "SELECT system_prompt, few_shots FROM task_templates WHERE id = ?",
        ("job_titles_es",),
    ).fetchone()
    few_shots = json.loads(template["few_shots"])
    system_prompt = build_system_prompt(template["system_prompt"], few_shots)

    # Create TitleInput objects
    title_inputs = [TitleInput(id="t001", title=retry_titles[0])]
    params = build_request_params(
        titles=title_inputs,
        system_prompt=system_prompt,
        taxonomy=None,
        titles_per_request=1,
    )
    retry_batch_id = fake_anthropic.submit_batch(params)

    # Insert retry batch and request
    from app.dao.batches import insert_batch
    from app.dao.batch_requests import insert_request

    insert_batch(
        conn,
        id=retry_batch_id,
        job_id=job_id,
        retry_round=1,
        parent_batch_id=batch.id,
        status="in_progress",
        request_count=1,
    )
    request_id = secrets.token_hex(16)
    insert_request(conn, id=request_id, batch_id=list_batches_for_job(conn, job_id)[-1].id, cluster_ids=[straggler_cluster_id])

    # Complete retry
    retry_batches = list_batches_for_job(conn, job_id)
    retry_batch = retry_batches[-1]
    retry_requests = list_requests_for_batch(conn, retry_batch.id)

    straggler_result = generate_dry_run_results(retry_cluster_ids, retry_titles)
    update_batch_status(conn, retry_batch.id, "ended")
    mark_request_completed(
        conn,
        retry_requests[0].id,
        raw_response=straggler_result.model_dump_json(),
    )
    update_cluster_answers(
        conn,
        straggler_cluster_id,
        male_es=straggler_result.results[0].male_es,
        female_es=straggler_result.results[0].female_es,
        category=straggler_result.results[0].category,
    )
    insert_spend(conn, job_id=job_id, batch_id=retry_batch.id, usd=0.0, at=int(time.time()))

    # Verify exactly 2 batches
    final_batches = list_batches_for_job(conn, job_id)
    assert len(final_batches) == 2, f"Expected 2 batches, got {len(final_batches)}"

    # Verify retry_round values
    retry_rounds = [b.retry_round for b in final_batches]
    assert retry_rounds == [0, 1], f"Expected retry_rounds [0, 1], got {retry_rounds}"


def test_stragglers_recovery_error_rows_is_zero(conn, fake_anthropic):
    """Straggler recovery results in completed job with error_rows == 0."""
    # Create 20 unique titles
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

    # Get clusters
    from app.dao.clusters import list_clusters

    clusters = list_clusters(conn, job_id)

    # Commit job
    commit_job(conn, fake_anthropic, job_id)

    # Get batch and requests
    from app.dao.batches import list_batches_for_job
    from app.dao.batch_requests import list_requests_for_batch

    batches = list_batches_for_job(conn, job_id)
    batch = batches[0]
    requests = list_requests_for_batch(conn, batch.id)

    # Generate results for all but last cluster
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

    # Complete first batch with N-1 results
    from app.dao.batches import update_batch_status
    from app.dao.batch_requests import mark_request_completed
    from app.dao.clusters import update_cluster_answers
    from app.dao.spend_log import insert_spend

    fake_result = generate_dry_run_results(results_cluster_ids, results_titles)
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

    # Submit retry batch
    retry_cluster_ids = [straggler_cluster_id]
    retry_titles = [cluster_titles[-1]]

    from app.anthropic.request_builder import build_request_params, build_system_prompt, TitleInput

    template = conn.execute(
        "SELECT system_prompt, few_shots FROM task_templates WHERE id = ?",
        ("job_titles_es",),
    ).fetchone()
    few_shots = json.loads(template["few_shots"])
    system_prompt = build_system_prompt(template["system_prompt"], few_shots)

    # Create TitleInput objects
    title_inputs = [TitleInput(id="t001", title=retry_titles[0])]
    params = build_request_params(
        titles=title_inputs,
        system_prompt=system_prompt,
        taxonomy=None,
        titles_per_request=1,
    )
    retry_batch_id = fake_anthropic.submit_batch(params)

    # Insert retry batch and request
    from app.dao.batches import insert_batch
    from app.dao.batch_requests import insert_request

    insert_batch(
        conn,
        id=retry_batch_id,
        job_id=job_id,
        retry_round=1,
        parent_batch_id=batch.id,
        status="in_progress",
        request_count=1,
    )
    request_id = secrets.token_hex(16)
    insert_request(conn, id=request_id, batch_id=list_batches_for_job(conn, job_id)[-1].id, cluster_ids=[straggler_cluster_id])

    # Complete retry
    retry_batches = list_batches_for_job(conn, job_id)
    retry_batch = retry_batches[-1]
    retry_requests = list_requests_for_batch(conn, retry_batch.id)

    straggler_result = generate_dry_run_results(retry_cluster_ids, retry_titles)
    update_batch_status(conn, retry_batch.id, "ended")
    mark_request_completed(
        conn,
        retry_requests[0].id,
        raw_response=straggler_result.model_dump_json(),
    )
    update_cluster_answers(
        conn,
        straggler_cluster_id,
        male_es=straggler_result.results[0].male_es,
        female_es=straggler_result.results[0].female_es,
        category=straggler_result.results[0].category,
    )
    insert_spend(conn, job_id=job_id, batch_id=retry_batch.id, usd=0.0, at=int(time.time()))

    # Transition to completed
    transition(conn, job_id, "completed", reason="test_completion")

    # Get job and verify error_rows == 0
    from app.dao.jobs import get_job

    job = get_job(conn, job_id)
    assert job.status == "completed", f"Expected status 'completed', got '{job.status}'"
    assert job.error_rows == 0, f"Expected error_rows == 0, got {job.error_rows}"

    # Verify no clusters have error set
    from app.dao.clusters import list_clusters

    final_clusters = list_clusters(conn, job_id)
    for cluster in final_clusters:
        assert (
            cluster.error is None or cluster.error == ""
        ), f"Cluster {cluster.id} has error '{cluster.error}'"
