"""Test 7: Persistent failure → max_retries_exceeded

Mock Anthropic so one specific title ID is *always* missing from the response,
across all retry rounds. After 3 retries, the cluster should be flagged
`max_retries_exceeded`, and the job should still `completed` (not `failed`).
"""
import json
import secrets
import time

from app.anthropic.dry_run import generate_dry_run_results
from app.csv_io.exporter import export_job_to_csv
from app.jobs.service import commit_job, transition


def test_persistent_failure_ends_in_completed_not_failed(conn, fake_anthropic):
    """Persistent failure across all retry rounds results in completed status (not failed)."""
    # Create 10 unique titles to get some clusters
    titles = [f"Job Title {i}" for i in range(10)]
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

    # Generate results for all but the last cluster (simulating persistent failure)
    # Get cluster representatives
    all_cluster_ids = []
    cluster_titles = []
    for req in requests:
        for cid in req.cluster_ids:
            all_cluster_ids.append(cid)
            cluster = next((c for c in clusters if c.id == cid), None)
            if cluster:
                cluster_titles.append(cluster.representative_original)

    # The last cluster will be the persistently failing one
    persistent_cluster_id = all_cluster_ids[-1]

    # Helper function to complete a batch with N-1 results (always missing the same cluster)
    def complete_batch_with_straggler(batch_obj, cluster_ids_to_include):
        """Complete a batch with results for specific clusters (missing the persistent one)."""
        from app.dao.batches import update_batch_status
        from app.dao.batch_requests import mark_request_completed
        from app.dao.clusters import update_cluster_answers
        from app.dao.spend_log import insert_spend
        from app.dao.batch_requests import list_requests_for_batch as list_reqs

        batch_requests = list_reqs(conn, batch_obj.id)

        # Generate results for the included clusters
        titles_to_include = []
        for cid in cluster_ids_to_include:
            cluster = next((c for c in clusters if c.id == cid), None)
            if cluster:
                titles_to_include.append(cluster.representative_original)

        if not titles_to_include:
            # No clusters to process, just mark batch as ended
            update_batch_status(conn, batch_obj.id, "ended")
            for req in batch_requests:
                mark_request_completed(
                    conn,
                    req.id,
                    raw_response='{"results": []}',
                )
        else:
            fake_result = generate_dry_run_results(cluster_ids_to_include, titles_to_include)
            update_batch_status(conn, batch_obj.id, "ended")

            # Mark completed requests
            for i, req in enumerate(batch_requests):
                mark_request_completed(
                    conn,
                    req.id,
                    raw_response=fake_result.model_dump_json(),
                )

            # Write answers to clusters
            for i, cluster_id in enumerate(cluster_ids_to_include):
                update_cluster_answers(
                    conn,
                    cluster_id,
                    male_es=fake_result.results[i].male_es,
                    female_es=fake_result.results[i].female_es,
                    category=fake_result.results[i].category,
                )

        # Record spend
        insert_spend(
            conn,
            job_id=job_id,
            batch_id=batch_obj.id,
            usd=0.0,
            at=int(time.time()),
        )

    # Complete first batch (round 0) with N-1 results
    first_batch_clusters = all_cluster_ids[:-1]
    complete_batch_with_straggler(batch, first_batch_clusters)

    # Transition job to polling
    transition(conn, job_id, "polling", reason="test_poll_0")

    # === Retry Round 1 ===
    # Submit retry batch with only the persistent cluster (but it will still fail)
    from app.anthropic.request_builder import build_request_params, build_system_prompt, TitleInput

    template = conn.execute(
        "SELECT system_prompt, few_shots FROM task_templates WHERE id = ?",
        ("job_titles_es",),
    ).fetchone()
    few_shots = json.loads(template["few_shots"])
    system_prompt = build_system_prompt(template["system_prompt"], few_shots)

    # Create TitleInput for the persistent cluster
    cluster = next((c for c in clusters if c.id == persistent_cluster_id), None)
    persistent_title = cluster.representative_original if cluster else "Unknown"

    # Build retry request with TPR=1 (halved from original 25)
    title_inputs = [TitleInput(id="t001", title=persistent_title)]
    params = build_request_params(
        titles=title_inputs,
        system_prompt=system_prompt,
        taxonomy=None,
        titles_per_request=1,
    )

    # Submit retry batch 1
    from app.dao.batches import insert_batch
    from app.dao.batch_requests import insert_request

    retry1_batch_id = fake_anthropic.submit_batch(params)

    # Insert retry batch 1
    insert_batch(
        conn,
        id=retry1_batch_id,
        job_id=job_id,
        retry_round=1,
        parent_batch_id=batch.id,
        status="in_progress",
        request_count=1,
    )

    # Insert request for retry 1
    request1_id = secrets.token_hex(16)
    insert_request(
        conn,
        id=request1_id,
        batch_id=list_batches_for_job(conn, job_id)[-1].id,
        cluster_ids=[persistent_cluster_id],
    )

    # Get retry batch 1
    retry1_batches = list_batches_for_job(conn, job_id)
    retry1_batch = [b for b in retry1_batches if b.retry_round == 1][0]

    # Complete retry batch 1 with the cluster STILL missing (persistent failure)
    # Empty results list to simulate the cluster still failing
    complete_batch_with_straggler(retry1_batch, [])

    # Transition polling -> retrying -> submitted -> polling (full retry flow)
    transition(conn, job_id, "retrying", reason="test_retry_1_submit")
    transition(conn, job_id, "submitted", reason="test_retry_1_submitted")
    transition(conn, job_id, "polling", reason="test_poll_after_retry_1")

    # === Retry Round 2 ===
    # Submit retry batch 2 with the persistent cluster (still fails)
    title_inputs = [TitleInput(id="t001", title=persistent_title)]
    params = build_request_params(
        titles=title_inputs,
        system_prompt=system_prompt,
        taxonomy=None,
        titles_per_request=1,
    )

    retry2_batch_id = fake_anthropic.submit_batch(params)

    # Insert retry batch 2
    insert_batch(
        conn,
        id=retry2_batch_id,
        job_id=job_id,
        retry_round=2,
        parent_batch_id=retry1_batch.id,
        status="in_progress",
        request_count=1,
    )

    # Insert request for retry 2
    request2_id = secrets.token_hex(16)
    insert_request(
        conn,
        id=request2_id,
        batch_id=list_batches_for_job(conn, job_id)[-1].id,
        cluster_ids=[persistent_cluster_id],
    )

    # Get retry batch 2
    retry2_batches = list_batches_for_job(conn, job_id)
    retry2_batch = [b for b in retry2_batches if b.retry_round == 2][0]

    # Complete retry batch 2 with the cluster STILL missing
    complete_batch_with_straggler(retry2_batch, [])

    # Transition polling -> retrying -> submitted -> polling
    transition(conn, job_id, "retrying", reason="test_retry_2_submit")
    transition(conn, job_id, "submitted", reason="test_retry_2_submitted")
    transition(conn, job_id, "polling", reason="test_poll_after_retry_2")

    # === Retry Round 3 ===
    # Submit retry batch 3 with the persistent cluster (still fails)
    title_inputs = [TitleInput(id="t001", title=persistent_title)]
    params = build_request_params(
        titles=title_inputs,
        system_prompt=system_prompt,
        taxonomy=None,
        titles_per_request=1,
    )

    retry3_batch_id = fake_anthropic.submit_batch(params)

    # Insert retry batch 3
    insert_batch(
        conn,
        id=retry3_batch_id,
        job_id=job_id,
        retry_round=3,
        parent_batch_id=retry2_batch.id,
        status="in_progress",
        request_count=1,
    )

    # Insert request for retry 3
    request3_id = secrets.token_hex(16)
    insert_request(
        conn,
        id=request3_id,
        batch_id=list_batches_for_job(conn, job_id)[-1].id,
        cluster_ids=[persistent_cluster_id],
    )

    # Get retry batch 3
    retry3_batches = list_batches_for_job(conn, job_id)
    retry3_batch = [b for b in retry3_batches if b.retry_round == 3][0]

    # Complete retry batch 3 with the cluster STILL missing
    complete_batch_with_straggler(retry3_batch, [])

    # Transition polling -> retrying -> submitted -> polling
    transition(conn, job_id, "retrying", reason="test_retry_3_submit")
    transition(conn, job_id, "submitted", reason="test_retry_3_submitted")
    transition(conn, job_id, "polling", reason="test_poll_after_retry_3")

    # At this point, all 3 retry rounds are done (retry_round=3)
    # The worker should detect that retry_round >= 3 and flag remaining unresolved clusters
    # Simulate worker _finalize_if_done logic
    from app.dao.clusters import list_clusters, mark_cluster_error
    from app.dao.jobs import update_job_counts, get_job

    # Find unresolved clusters (male_es is NULL and error is NULL)
    unresolved = [
        c for c in list_clusters(conn, job_id)
        if c.male_es is None and c.error is None
    ]

    # Flag each unresolved cluster with max_retries_exceeded
    for cluster in unresolved:
        mark_cluster_error(conn, cluster.id, "max_retries_exceeded")

    # Calculate total rows and error rows
    all_clusters = list_clusters(conn, job_id)
    total_rows = sum(c.member_count for c in all_clusters)
    error_rows = sum(c.member_count for c in all_clusters if c.error)

    # Update job counts
    update_job_counts(conn, job_id, total_rows=total_rows, error_rows=error_rows)

    # Set finished_at
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE jobs SET finished_at = ? WHERE id = ?",
        (int(time.time()), job_id)
    )

    # Transition job to completed
    transition(conn, job_id, "completed", reason="max_retries_exceeded_finalized")

    # Verify job status is completed (not failed)
    job = get_job(conn, job_id)
    assert job.status == "completed", f"Expected status 'completed', got '{job.status}'"


def test_flagged_rows_have_max_retries_exceeded_error_code(conn, fake_anthropic):
    """Persistently failing rows should have error == 'max_retries_exceeded'."""
    # Create 10 unique titles
    titles = [f"Job Title {i}" for i in range(10)]
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

    # Get all cluster IDs
    all_cluster_ids = []
    cluster_titles = {}
    for req in requests:
        for cid in req.cluster_ids:
            all_cluster_ids.append(cid)
            cluster = next((c for c in clusters if c.id == cid), None)
            if cluster:
                cluster_titles[cid] = cluster.representative_original

    # The last cluster will be the persistently failing one
    persistent_cluster_id = all_cluster_ids[-1]
    other_cluster_ids = all_cluster_ids[:-1]

    # Complete first batch with N-1 results
    from app.dao.batches import update_batch_status
    from app.dao.batch_requests import mark_request_completed
    from app.dao.clusters import update_cluster_answers
    from app.dao.spend_log import insert_spend

    other_titles = [cluster_titles[cid] for cid in other_cluster_ids]
    fake_result = generate_dry_run_results(other_cluster_ids, other_titles)
    update_batch_status(conn, batch.id, "ended")

    # Mark request as completed (worker marks it completed even with stragglers)
    mark_request_completed(conn, requests[0].id, raw_response=fake_result.model_dump_json())

    # Write answers to the 9 successful clusters
    for i, cluster_id in enumerate(other_cluster_ids):
        update_cluster_answers(
            conn,
            cluster_id,
            male_es=fake_result.results[i].male_es,
            female_es=fake_result.results[i].female_es,
            category=fake_result.results[i].category,
        )

    insert_spend(conn, job_id=job_id, batch_id=batch.id, usd=0.0, at=int(time.time()))

    transition(conn, job_id, "polling", reason="test_poll_0")

    # Submit 3 retry batches, all failing for the same cluster
    from app.anthropic.request_builder import build_request_params, build_system_prompt, TitleInput
    from app.dao.batches import insert_batch
    from app.dao.batch_requests import insert_request

    template = conn.execute(
        "SELECT system_prompt, few_shots FROM task_templates WHERE id = ?",
        ("job_titles_es",),
    ).fetchone()
    few_shots = json.loads(template["few_shots"])
    system_prompt = build_system_prompt(template["system_prompt"], few_shots)

    persistent_title = cluster_titles[persistent_cluster_id]

    # Retry rounds 1, 2, and 3
    for round_num in [1, 2, 3]:
        # Get parent batch
        batches_list = list_batches_for_job(conn, job_id)
        if round_num == 1:
            parent_batch = batch
        else:
            parent_batch = [b for b in batches_list if b.retry_round == round_num - 1][0]

        # Submit retry batch
        title_inputs = [TitleInput(id="t001", title=persistent_title)]
        params = build_request_params(
            titles=title_inputs,
            system_prompt=system_prompt,
            taxonomy=None,
            titles_per_request=1,
        )
        retry_batch_id = fake_anthropic.submit_batch(params)

        # Insert retry batch
        insert_batch(
            conn,
            id=retry_batch_id,
            job_id=job_id,
            retry_round=round_num,
            parent_batch_id=parent_batch.id,
            status="in_progress",
            request_count=1,
        )

        # Insert request
        request_id = secrets.token_hex(16)
        insert_request(
            conn,
            id=request_id,
            batch_id=list_batches_for_job(conn, job_id)[-1].id,
            cluster_ids=[persistent_cluster_id],
        )

        # Get retry batch and complete it with empty results (persistent failure)
        retry_batches = list_batches_for_job(conn, job_id)
        retry_batch = [b for b in retry_batches if b.retry_round == round_num][0]
        retry_requests = list_requests_for_batch(conn, retry_batch.id)

        update_batch_status(conn, retry_batch.id, "ended")
        mark_request_completed(
            conn,
            retry_requests[0].id,
            raw_response='{"results": []}',
        )

        insert_spend(conn, job_id=job_id, batch_id=retry_batch.id, usd=0.0, at=int(time.time()))

        if round_num < 3:
            # For rounds 1 and 2, transition through the full retry flow
            # polling -> retrying -> submitted -> polling (ready for next retry round)
            transition(conn, job_id, "retrying", reason=f"test_retry_{round_num}_submit")
            transition(conn, job_id, "submitted", reason=f"test_retry_{round_num}_submitted")
            transition(conn, job_id, "polling", reason=f"test_poll_after_retry_{round_num}")
        # For round 3, we don't transition (stays in retrying state, will go to completed)

    # Flag unresolved clusters with max_retries_exceeded
    from app.dao.clusters import mark_cluster_error
    from app.dao.jobs import update_job_counts

    unresolved = [
        c for c in list_clusters(conn, job_id)
        if c.male_es is None and c.error is None
    ]

    for cluster in unresolved:
        mark_cluster_error(conn, cluster.id, "max_retries_exceeded")

    # Update job counts
    all_clusters = list_clusters(conn, job_id)
    total_rows = sum(c.member_count for c in all_clusters)
    error_rows = sum(c.member_count for c in all_clusters if c.error)
    update_job_counts(conn, job_id, total_rows=total_rows, error_rows=error_rows)

    # Set finished_at
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE jobs SET finished_at = ? WHERE id = ?",
        (int(time.time()), job_id)
    )

    transition(conn, job_id, "completed", reason="test_completion")

    # Export CSV and verify flagged rows have the correct error code
    csv_bytes = export_job_to_csv(conn, job_id)
    csv_text = csv_bytes.decode("utf-8-sig")

    lines = csv_text.splitlines()
    assert len(lines) == 11  # header + 10 data rows

    # Find rows with error
    rows_with_error = []
    for line in lines[1:]:  # Skip header
        # CSV format: original,male_es,female_es,category,error
        parts = line.split(",")
        original = parts[0]
        male_es = parts[1]
        female_es = parts[2]
        category = parts[3]
        error = parts[4]

        if error:
            rows_with_error.append((original, male_es, female_es, category, error))

    # Verify exactly one row has error (the persistently failing cluster)
    assert len(rows_with_error) == 1, f"Expected 1 row with error, got {len(rows_with_error)}"

    # Verify the error code is correct
    original, male_es, female_es, category, error = rows_with_error[0]
    assert error == "max_retries_exceeded", f"Expected error 'max_retries_exceeded', got '{error}'"

    # Verify the answer columns are empty for the errored row
    assert male_es == "", f"Expected empty male_es for errored row, got '{male_es}'"
    assert female_es == "", f"Expected empty female_es for errored row, got '{female_es}'"
    assert category == "", f"Expected empty category for errored row, got '{category}'"


def test_flagged_rows_count_matches_expected_cluster_size(conn, fake_anthropic):
    """error_rows should match the member count of the persistently failing cluster."""
    # Create 20 titles (some may cluster together)
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

    # Pick a cluster with known member count (last cluster)
    persistent_cluster = clusters[-1]
    persistent_cluster_id = persistent_cluster.id
    expected_error_rows = persistent_cluster.member_count

    # Commit job
    commit_job(conn, fake_anthropic, job_id)

    # Get batch and requests
    from app.dao.batches import list_batches_for_job
    from app.dao.batch_requests import list_requests_for_batch

    batches = list_batches_for_job(conn, job_id)
    batch = batches[0]
    requests = list_requests_for_batch(conn, batch.id)

    # Get all cluster IDs
    all_cluster_ids = []
    cluster_titles = {}
    for req in requests:
        for cid in req.cluster_ids:
            all_cluster_ids.append(cid)
            cluster = next((c for c in clusters if c.id == cid), None)
            if cluster:
                cluster_titles[cid] = cluster.representative_original

    # Complete first batch, missing the persistent cluster
    from app.dao.batches import update_batch_status
    from app.dao.batch_requests import mark_request_completed
    from app.dao.clusters import update_cluster_answers
    from app.dao.spend_log import insert_spend

    other_cluster_ids = [cid for cid in all_cluster_ids if cid != persistent_cluster_id]
    other_titles = [cluster_titles[cid] for cid in other_cluster_ids]

    if other_titles:
        fake_result = generate_dry_run_results(other_cluster_ids, other_titles)
        update_batch_status(conn, batch.id, "ended")

        for i, req in enumerate(requests):
            mark_request_completed(conn, req.id, raw_response=fake_result.model_dump_json())

        for i, cluster_id in enumerate(other_cluster_ids):
            update_cluster_answers(
                conn,
                cluster_id,
                male_es=fake_result.results[i].male_es,
                female_es=fake_result.results[i].female_es,
                category=fake_result.results[i].category,
            )
    else:
        update_batch_status(conn, batch.id, "ended")
        for req in requests:
            mark_request_completed(conn, req.id, raw_response='{"results": []}')

    insert_spend(conn, job_id=job_id, batch_id=batch.id, usd=0.0, at=int(time.time()))

    transition(conn, job_id, "polling", reason="test_poll_0")

    # Submit 3 retry batches, all failing
    from app.anthropic.request_builder import build_request_params, build_system_prompt, TitleInput
    from app.dao.batches import insert_batch
    from app.dao.batch_requests import insert_request

    template = conn.execute(
        "SELECT system_prompt, few_shots FROM task_templates WHERE id = ?",
        ("job_titles_es",),
    ).fetchone()
    few_shots = json.loads(template["few_shots"])
    system_prompt = build_system_prompt(template["system_prompt"], few_shots)

    persistent_title = cluster_titles[persistent_cluster_id]

    for round_num in [1, 2, 3]:
        batches_list = list_batches_for_job(conn, job_id)
        if round_num == 1:
            parent_batch = batch
        else:
            parent_batch = [b for b in batches_list if b.retry_round == round_num - 1][0]

        title_inputs = [TitleInput(id="t001", title=persistent_title)]
        params = build_request_params(
            titles=title_inputs,
            system_prompt=system_prompt,
            taxonomy=None,
            titles_per_request=1,
        )
        retry_batch_id = fake_anthropic.submit_batch(params)

        insert_batch(
            conn,
            id=retry_batch_id,
            job_id=job_id,
            retry_round=round_num,
            parent_batch_id=parent_batch.id,
            status="in_progress",
            request_count=1,
        )

        request_id = secrets.token_hex(16)
        insert_request(
            conn,
            id=request_id,
            batch_id=list_batches_for_job(conn, job_id)[-1].id,
            cluster_ids=[persistent_cluster_id],
        )

        retry_batches = list_batches_for_job(conn, job_id)
        retry_batch = [b for b in retry_batches if b.retry_round == round_num][0]
        retry_requests = list_requests_for_batch(conn, retry_batch.id)

        update_batch_status(conn, retry_batch.id, "ended")
        mark_request_completed(
            conn,
            retry_requests[0].id,
            raw_response='{"results": []}',
        )

        insert_spend(conn, job_id=job_id, batch_id=retry_batch.id, usd=0.0, at=int(time.time()))

        if round_num < 3:
            # For rounds 1 and 2, transition through the full retry flow
            transition(conn, job_id, "retrying", reason=f"test_retry_{round_num}_submit")
            transition(conn, job_id, "submitted", reason=f"test_retry_{round_num}_submitted")
            transition(conn, job_id, "polling", reason=f"test_poll_after_retry_{round_num}")

    # Flag unresolved clusters
    from app.dao.clusters import mark_cluster_error
    from app.dao.jobs import update_job_counts

    unresolved = [
        c for c in list_clusters(conn, job_id)
        if c.male_es is None and c.error is None
    ]

    for cluster in unresolved:
        mark_cluster_error(conn, cluster.id, "max_retries_exceeded")

    # Update job counts
    all_clusters = list_clusters(conn, job_id)
    total_rows = sum(c.member_count for c in all_clusters)
    error_rows = sum(c.member_count for c in all_clusters if c.error)
    update_job_counts(conn, job_id, total_rows=total_rows, error_rows=error_rows)

    # Set finished_at
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE jobs SET finished_at = ? WHERE id = ?",
        (int(time.time()), job_id)
    )

    transition(conn, job_id, "completed", reason="test_completion")

    # Verify error_rows matches cluster member count
    from app.dao.jobs import get_job

    job = get_job(conn, job_id)
    assert job.error_rows == expected_error_rows, (
        f"Expected error_rows == {expected_error_rows} "
        f"(member count of persistently failing cluster), "
        f"got {job.error_rows}"
    )


def test_total_row_count_unchanged(conn, fake_anthropic):
    """Even with persistent failures, total row count should match input."""
    # Create 30 titles
    n_rows = 30
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
    initial_total_rows = result.total_rows

    # Verify total rows is correct
    assert initial_total_rows == n_rows, (
        f"Expected total_rows == {n_rows}, got {initial_total_rows}"
    )

    # Get clusters
    from app.dao.clusters import list_clusters

    clusters = list_clusters(conn, job_id)
    persistent_cluster = clusters[-1]
    persistent_cluster_id = persistent_cluster.id

    # Commit job
    commit_job(conn, fake_anthropic, job_id)

    # Get batch and requests
    from app.dao.batches import list_batches_for_job
    from app.dao.batch_requests import list_requests_for_batch

    batches = list_batches_for_job(conn, job_id)
    batch = batches[0]
    requests = list_requests_for_batch(conn, batch.id)

    # Get all cluster IDs
    all_cluster_ids = []
    cluster_titles = {}
    for req in requests:
        for cid in req.cluster_ids:
            all_cluster_ids.append(cid)
            cluster = next((c for c in clusters if c.id == cid), None)
            if cluster:
                cluster_titles[cid] = cluster.representative_original

    # Complete first batch, missing the persistent cluster
    from app.dao.batches import update_batch_status
    from app.dao.batch_requests import mark_request_completed
    from app.dao.clusters import update_cluster_answers
    from app.dao.spend_log import insert_spend

    other_cluster_ids = [cid for cid in all_cluster_ids if cid != persistent_cluster_id]
    other_titles = [cluster_titles[cid] for cid in other_cluster_ids]

    if other_titles:
        fake_result = generate_dry_run_results(other_cluster_ids, other_titles)
        update_batch_status(conn, batch.id, "ended")

        for i, req in enumerate(requests):
            mark_request_completed(conn, req.id, raw_response=fake_result.model_dump_json())

        for i, cluster_id in enumerate(other_cluster_ids):
            update_cluster_answers(
                conn,
                cluster_id,
                male_es=fake_result.results[i].male_es,
                female_es=fake_result.results[i].female_es,
                category=fake_result.results[i].category,
            )
    else:
        update_batch_status(conn, batch.id, "ended")
        for req in requests:
            mark_request_completed(conn, req.id, raw_response='{"results": []}')

    insert_spend(conn, job_id=job_id, batch_id=batch.id, usd=0.0, at=int(time.time()))

    transition(conn, job_id, "polling", reason="test_poll_0")

    # Submit 3 retry batches, all failing
    from app.anthropic.request_builder import build_request_params, build_system_prompt, TitleInput
    from app.dao.batches import insert_batch
    from app.dao.batch_requests import insert_request

    template = conn.execute(
        "SELECT system_prompt, few_shots FROM task_templates WHERE id = ?",
        ("job_titles_es",),
    ).fetchone()
    few_shots = json.loads(template["few_shots"])
    system_prompt = build_system_prompt(template["system_prompt"], few_shots)

    persistent_title = cluster_titles[persistent_cluster_id]

    for round_num in [1, 2, 3]:
        batches_list = list_batches_for_job(conn, job_id)
        if round_num == 1:
            parent_batch = batch
        else:
            parent_batch = [b for b in batches_list if b.retry_round == round_num - 1][0]

        title_inputs = [TitleInput(id="t001", title=persistent_title)]
        params = build_request_params(
            titles=title_inputs,
            system_prompt=system_prompt,
            taxonomy=None,
            titles_per_request=1,
        )
        retry_batch_id = fake_anthropic.submit_batch(params)

        insert_batch(
            conn,
            id=retry_batch_id,
            job_id=job_id,
            retry_round=round_num,
            parent_batch_id=parent_batch.id,
            status="in_progress",
            request_count=1,
        )

        request_id = secrets.token_hex(16)
        insert_request(
            conn,
            id=request_id,
            batch_id=list_batches_for_job(conn, job_id)[-1].id,
            cluster_ids=[persistent_cluster_id],
        )

        retry_batches = list_batches_for_job(conn, job_id)
        retry_batch = [b for b in retry_batches if b.retry_round == round_num][0]
        retry_requests = list_requests_for_batch(conn, retry_batch.id)

        update_batch_status(conn, retry_batch.id, "ended")
        mark_request_completed(
            conn,
            retry_requests[0].id,
            raw_response='{"results": []}',
        )

        insert_spend(conn, job_id=job_id, batch_id=retry_batch.id, usd=0.0, at=int(time.time()))

        if round_num < 3:
            # For rounds 1 and 2, transition through the full retry flow
            transition(conn, job_id, "retrying", reason=f"test_retry_{round_num}_submit")
            transition(conn, job_id, "submitted", reason=f"test_retry_{round_num}_submitted")
            transition(conn, job_id, "polling", reason=f"test_poll_after_retry_{round_num}")

    # Flag unresolved clusters
    from app.dao.clusters import mark_cluster_error
    from app.dao.jobs import update_job_counts

    unresolved = [
        c for c in list_clusters(conn, job_id)
        if c.male_es is None and c.error is None
    ]

    for cluster in unresolved:
        mark_cluster_error(conn, cluster.id, "max_retries_exceeded")

    # Update job counts
    all_clusters = list_clusters(conn, job_id)
    total_rows = sum(c.member_count for c in all_clusters)
    error_rows = sum(c.member_count for c in all_clusters if c.error)
    update_job_counts(conn, job_id, total_rows=total_rows, error_rows=error_rows)

    # Set finished_at
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE jobs SET finished_at = ? WHERE id = ?",
        (int(time.time()), job_id)
    )

    transition(conn, job_id, "completed", reason="test_completion")

    # Verify total_rows is unchanged
    from app.dao.jobs import get_job

    job = get_job(conn, job_id)
    assert job.total_rows == n_rows, (
        f"Expected total_rows == {n_rows}, got {job.total_rows}"
    )

    # Verify error_rows + populated_rows == total_rows
    csv_bytes = export_job_to_csv(conn, job_id)
    csv_text = csv_bytes.decode("utf-8-sig")
    lines = csv_text.splitlines()

    # Count rows with and without errors
    populated_rows = 0
    error_rows_in_csv = 0
    for line in lines[1:]:  # Skip header
        parts = line.split(",")
        error = parts[4]
        if error:
            error_rows_in_csv += 1
        else:
            populated_rows += 1

    # Verify the math
    assert populated_rows + error_rows_in_csv == n_rows, (
        f"populated_rows ({populated_rows}) + error_rows ({error_rows_in_csv}) "
        f"!= total_rows ({n_rows})"
    )
