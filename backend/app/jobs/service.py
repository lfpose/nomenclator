import logging
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.anthropic.request_builder import TitleInput, build_request_params, build_system_prompt
from app.cluster.pipeline import run_clustering
from app.csv_io.ingest import ingest
from app.dao import batches as batches_dao
from app.dao import batch_requests as batch_requests_dao
from app.dao import clusters as clusters_dao
from app.dao import job_rows as job_rows_dao
from app.dao import jobs as jobs_dao
from app.dao import task_templates as task_templates_dao
from app.jobs.estimator import check_cap, estimate_job_cost
from app.jobs.state_machine import assert_allowed

if TYPE_CHECKING:
    from app.dao.clusters import Cluster

if TYPE_CHECKING:
    from sqlite3 import Connection

log = logging.getLogger("nomenclator.jobs")


class ConcurrencyError(Exception):
    """Raised when a job cannot start because another job is already running."""
    pass


class SpendCapExceeded(Exception):
    """Raised when estimated cost would exceed monthly spend cap."""
    pass


def transition(conn, job_id: str, new_status: str, reason: str) -> None:
    """Transition a job to a new status with validation and logging."""
    job = jobs_dao.get_job(conn, job_id)
    if job is None:
        raise ValueError(f"job not found: {job_id}")
    assert_allowed(job.status, new_status)
    jobs_dao.update_job_status(conn, job_id, new_status)
    log.info(
        "job.transition",
        extra={"job_id": job_id, "from": job.status, "to": new_status, "reason": reason},
    )


def assert_no_running_job(conn) -> None:
    """Raise ConcurrencyError if any non-terminal job exists."""
    if jobs_dao.count_active_jobs(conn) > 0:
        raise ConcurrencyError("job_already_running")


@dataclass(frozen=True)
class PreviewResult:
    """Result of creating a preview job."""
    job_id: str
    total_rows: int
    exact_unique_rows: int
    cluster_count: int
    largest_cluster_size: int
    est_cost_usd: float
    top_clusters: list[dict]  # {representative, member_count, members}
    warnings: list[dict]  # {type, cluster_id, ...}


def create_preview_job(
    conn: "Connection",
    *,
    file_bytes: bytes | None = None,
    text: str | None = None,
    threshold: int = 90,
    titles_per_request: int = 25,
) -> PreviewResult:
    """Create a preview job by ingesting, clustering, and persisting data.

    Args:
        conn: Database connection
        file_bytes: Raw bytes of a CSV file (optional)
        text: Pasted text with one title per line (optional)
        threshold: Clustering similarity threshold (0-100)
        titles_per_request: Number of titles per Anthropic batch request

    Returns:
        PreviewResult with job details, cost estimate, and top clusters

    Raises:
        CSVError: If input parsing or validation fails
        ValueError: If neither file_bytes nor text is provided
    """
    # Step 1: Ingest and normalize input
    rows = ingest(file_bytes=file_bytes, text=text)
    total_rows = len(rows)

    # Step 2: Run clustering
    cluster_results = run_clustering(rows, threshold)
    cluster_count = len(cluster_results)

    # Step 3: Create job in 'draft' state
    job_id = jobs_dao.create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=threshold,
        titles_per_request=titles_per_request,
    )

    # Step 4: Bulk insert job rows
    job_rows_dao.bulk_insert_rows(conn, job_id, rows)

    # Step 5: Insert clusters and assign to rows
    warnings: list[dict] = []
    largest_cluster_size = 0

    # Fetch all inserted job rows with their IDs (ordered by row_index)
    all_job_rows = job_rows_dao.list_rows(conn, job_id)
    row_id_by_index: dict[int, int] = {r.row_index: r.id for r in all_job_rows}

    for cluster in cluster_results:
        # Insert cluster
        cluster_db_id = clusters_dao.insert_cluster(
            conn,
            job_id=job_id,
            representative_original=cluster.representative_original,
            normalized_key=cluster.normalized_key,
            member_count=cluster.member_count,
        )

        # Track largest cluster
        if cluster.member_count > largest_cluster_size:
            largest_cluster_size = cluster.member_count

        # Emit warning for large clusters (above 50)
        if cluster.member_count > 50:
            warnings.append({
                "type": "large_cluster",
                "cluster_id": cluster_db_id,
                "representative": cluster.representative_original,
                "member_count": cluster.member_count,
            })

        # Assign cluster to rows
        row_ids = [row_id_by_index[idx] for idx in cluster.member_row_indices]
        # The representative row is the one with the representative_original text
        rep_row_id: int | None = None
        for row_idx in cluster.member_row_indices:
            row_data = all_job_rows[row_idx]  # rows are ordered by row_index
            if row_data.original == cluster.representative_original:
                rep_row_id = row_data.id
                break

        job_rows_dao.assign_cluster(conn, row_ids, cluster_db_id, rep_row_id)

    # Step 6: Compute cost estimate
    est_cost = estimate_job_cost(cluster_count, titles_per_request)

    # Step 7: Calculate exact unique rows (after dedup)
    exact_unique = len(set(normalized for _, _, normalized in rows))

    # Step 8: Update job counts
    jobs_dao.update_job_counts(
        conn,
        job_id=job_id,
        total_rows=total_rows,
        exact_unique_rows=exact_unique,
        cluster_count=cluster_count,
        est_cost_usd=est_cost,
    )

    # Step 9: Transition to 'preview' state
    transition(conn, job_id, "preview", reason="preview_created")

    # Step 10: Build top clusters (largest 10)
    sorted_clusters = sorted(cluster_results, key=lambda c: c.member_count, reverse=True)[:10]
    top_clusters = [
        {
            "representative": c.representative_original,
            "member_count": c.member_count,
            "members": [
                all_job_rows[idx].original
                for idx in sorted(c.member_row_indices)
            ],
        }
        for c in sorted_clusters
    ]

    return PreviewResult(
        job_id=job_id,
        total_rows=total_rows,
        exact_unique_rows=exact_unique,
        cluster_count=cluster_count,
        largest_cluster_size=largest_cluster_size,
        est_cost_usd=est_cost,
        top_clusters=top_clusters,
        warnings=warnings,
    )


def recluster_job(
    conn: "Connection",
    job_id: str,
    threshold: int,
) -> PreviewResult:
    """Recluster an existing job with a new threshold.

    Args:
        conn: Database connection
        job_id: ID of the job to recluster
        threshold: New clustering similarity threshold (0-100)

    Returns:
        PreviewResult with updated job details and top clusters

    Raises:
        ValueError: If job not found or not in preview state
    """
    # Step 1: Validate job is in preview state
    job = jobs_dao.get_job(conn, job_id)
    if job is None:
        raise ValueError(f"job not found: {job_id}")
    if job.status != "preview":
        raise ValueError(f"invalid_state: job must be in preview state, got {job.status}")

    # Step 2: Fetch existing job rows with cached normalized values
    all_job_rows = job_rows_dao.list_rows(conn, job_id)
    if not all_job_rows:
        raise ValueError(f"no rows found for job: {job_id}")

    # Reconstruct rows list for clustering
    rows = [(r.row_index, r.original, r.normalized) for r in all_job_rows]

    # Step 3: Delete old clusters
    clusters_dao.delete_clusters_for_job(conn, job_id)

    # Step 4: Clear cluster assignments from job rows
    job_rows_dao.clear_clusters(conn, job_id)

    # Step 5: Run clustering with new threshold
    cluster_results = run_clustering(rows, threshold)
    cluster_count = len(cluster_results)

    # Step 6: Update job's fuzzy_threshold
    conn.execute(
        "UPDATE jobs SET fuzzy_threshold = ? WHERE id = ?",
        (threshold, job_id),
    )

    # Step 7: Insert new clusters and assign to rows
    warnings: list[dict] = []
    largest_cluster_size = 0

    # Re-fetch job rows after clearing (still have same IDs)
    fresh_job_rows = job_rows_dao.list_rows(conn, job_id)
    row_id_by_index: dict[int, int] = {r.row_index: r.id for r in fresh_job_rows}

    for cluster in cluster_results:
        # Insert cluster
        cluster_db_id = clusters_dao.insert_cluster(
            conn,
            job_id=job_id,
            representative_original=cluster.representative_original,
            normalized_key=cluster.normalized_key,
            member_count=cluster.member_count,
        )

        # Track largest cluster
        if cluster.member_count > largest_cluster_size:
            largest_cluster_size = cluster.member_count

        # Emit warning for large clusters (above 50)
        if cluster.member_count > 50:
            warnings.append({
                "type": "large_cluster",
                "cluster_id": cluster_db_id,
                "representative": cluster.representative_original,
                "member_count": cluster.member_count,
            })

        # Assign cluster to rows
        row_ids = [row_id_by_index[idx] for idx in cluster.member_row_indices]
        # Find representative row ID
        rep_row_id: int | None = None
        for row_idx in cluster.member_row_indices:
            row_data = fresh_job_rows[row_idx]  # rows are ordered by row_index
            if row_data.original == cluster.representative_original:
                rep_row_id = row_data.id
                break

        job_rows_dao.assign_cluster(conn, row_ids, cluster_db_id, rep_row_id)

    # Step 8: Compute cost estimate
    est_cost = estimate_job_cost(cluster_count, job.titles_per_request)

    # Step 9: Calculate exact unique rows
    exact_unique = len(set(normalized for _, _, normalized in rows))

    # Step 10: Update job counts
    jobs_dao.update_job_counts(
        conn,
        job_id=job_id,
        exact_unique_rows=exact_unique,
        cluster_count=cluster_count,
        est_cost_usd=est_cost,
    )

    # Step 11: Build top clusters (largest 10)
    sorted_clusters = sorted(cluster_results, key=lambda c: c.member_count, reverse=True)[:10]
    top_clusters = [
        {
            "representative": c.representative_original,
            "member_count": c.member_count,
            "members": [
                fresh_job_rows[idx].original
                for idx in sorted(c.member_row_indices)
            ],
        }
        for c in sorted_clusters
    ]

    # Return PreviewResult (job_id, total_rows unchanged)
    return PreviewResult(
        job_id=job_id,
        total_rows=job.total_rows,
        exact_unique_rows=exact_unique,
        cluster_count=cluster_count,
        largest_cluster_size=largest_cluster_size,
        est_cost_usd=est_cost,
        top_clusters=top_clusters,
        warnings=warnings,
    )


def commit_job(
    conn: "Connection",
    client,  # AnthropicBatchClient (protocol)
    job_id: str,
    *,
    prompt_override: str | None = None,
    taxonomy: str | None = None,
    titles_per_request: int | None = None,
) -> None:
    """Commit a previewed job for processing by Anthropic.

    Args:
        conn: Database connection
        client: Anthropic batch client (real or fake)
        job_id: ID of the job to commit
        prompt_override: Optional custom system prompt
        taxonomy: Optional taxonomy string for categories
        titles_per_request: Number of titles per request (uses job default if None)

    Raises:
        ValueError: If job not found, invalid state, or other validation errors
        ConcurrencyError: If another job is already running
        SpendCapExceeded: If estimated cost would exceed monthly cap
    """
    # Step 1: Validate job is in preview state
    job = jobs_dao.get_job(conn, job_id)
    if job is None:
        raise ValueError(f"job not found: {job_id}")
    if job.status != "preview":
        raise ValueError(f"invalid_state: job must be in preview state, got {job.status}")

    # Step 2: Check for concurrent jobs
    assert_no_running_job(conn)

    # Step 3: Load job configuration
    template = task_templates_dao.get_template(conn, job.task_template_id)
    if template is None:
        raise ValueError(f"template not found: {job.task_template_id}")

    if titles_per_request is None:
        titles_per_request = job.titles_per_request

    # Step 4: Load clusters
    clusters = clusters_dao.list_clusters(conn, job_id)
    if not clusters:
        raise ValueError(f"no clusters found for job: {job_id}")

    # Step 5: Build TitleInput groups of size titles_per_request
    cluster_groups: list[list[Cluster]] = []
    for i in range(0, len(clusters), titles_per_request):
        cluster_groups.append(clusters[i:i + titles_per_request])

    # Step 6: Build request params for each group
    all_requests: list[dict] = []
    system_prompt = prompt_override if prompt_override is not None else template.system_prompt
    built_system_prompt = build_system_prompt(system_prompt, template.few_shots)

    for group in cluster_groups:
        titles = [
            TitleInput(
                id=f"t{cluster.id:03d}",
                title=cluster.representative_original,
            )
            for cluster in group
        ]
        # Note: build_request_params requires len(titles) == titles_per_request,
        # but we allow the last group to be smaller. We'll build with the actual size.
        params = build_request_params(
            titles=titles,
            system_prompt=built_system_prompt,
            taxonomy=taxonomy,
            titles_per_request=len(titles),  # Use actual group size
        )
        all_requests.append(params)

    # Step 7: Compute estimated cost
    estimated_cost = estimate_job_cost(len(clusters), titles_per_request)

    # Step 8: Check spend cap
    cap_check = check_cap(conn, estimated_cost)
    if not cap_check.ok:
        raise SpendCapExceeded(
            f"Monthly cap ${cap_check.cap_usd} would be exceeded "
            f"(used: ${cap_check.used_usd:.2f}, estimated: ${cap_check.estimated_usd:.2f})"
        )

    # Step 9: Transition to queued state before submitting
    transition(conn, job_id, "queued", reason="commit_start")

    # Step 10: Submit batch to Anthropic
    batch_id = client.submit_batch(all_requests)

    # Step 11: Persist batch row
    batches_dao.insert_batch(
        conn,
        id=batch_id,
        job_id=job_id,
        retry_round=0,
        parent_batch_id=None,
        status="in_progress",
        request_count=len(cluster_groups),
    )

    # Step 12: Persist batch_requests rows with cluster_ids
    for i, group in enumerate(cluster_groups):
        request_id = str(uuid.uuid4())
        cluster_ids = [cluster.id for cluster in group]
        batch_requests_dao.insert_request(
            conn,
            id=request_id,
            batch_id=batch_id,
            cluster_ids=cluster_ids,
        )

    # Step 13: Transition job to submitted
    transition(conn, job_id, "submitted", reason="commit")


def cancel_job(
    conn: "Connection",
    client,  # AnthropicBatchClient (protocol)
    job_id: str,
) -> None:
    """Cancel a job in a cancellable state.

    Args:
        conn: Database connection
        client: Anthropic batch client (real or fake)
        job_id: ID of the job to cancel

    Raises:
        ValueError: If job not found or not in a cancellable state
    """
    # Step 1: Validate job exists
    job = jobs_dao.get_job(conn, job_id)
    if job is None:
        raise ValueError("job_not_found")

    # Step 2: Validate job is in cancellable state
    if job.status not in {"queued", "submitted", "polling", "retrying"}:
        raise ValueError(
            f"invalid_state: job must be in queued, submitted, polling, or retrying state, got {job.status}"
        )

    # Step 3: Cancel any non-terminal batches upstream
    batches = batches_dao.list_batches_for_job(conn, job_id)
    for batch in batches:
        if batch.status not in {"ended", "canceled", "expired"}:
            try:
                client.cancel_batch(batch.id)
            except Exception:
                # Best effort - swallow errors from Anthropic cancel
                pass

    # Step 4: Transition job to cancelled
    transition(conn, job_id, "cancelled", reason="operator_cancel")
