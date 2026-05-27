from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.anthropic.request_builder import TitleInput, build_request_params, build_system_prompt
from app.cluster.pipeline import run_clustering, compute_embeddings_for_rows
from app.csv_io.normalize import normalize as _normalize
from app.settings import settings as app_settings
from app.csv_io.ingest import ingest
from app.dao import batches as batches_dao
from app.dao import batch_requests as batch_requests_dao
from app.dao import clusters as clusters_dao
from app.dao import embeddings_cache as embeddings_cache_dao
from app.dao import job_rows as job_rows_dao
from app.dao import jobs as jobs_dao
from app.dao import task_templates as task_templates_dao
from app.jobs.estimator import check_cap, estimate_job_cost
from app.jobs.state_machine import assert_allowed

if TYPE_CHECKING:
    from app.anthropic.review import PromptReview
    from app.dao.clusters import Cluster
    from sqlite3 import Connection

log = logging.getLogger("nomenclator.jobs")


class ConcurrencyError(Exception):
    """Raised when a job cannot start because another job is already running."""
    pass


class SpendCapExceeded(Exception):
    """Raised when estimated cost would exceed monthly spend cap."""
    pass


class APIError(Exception):
    """Raised when an external API call fails."""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


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
    total_input_rows: int  # Before subset
    selected_rows: int  # After subset
    exact_unique_rows: int
    cluster_count: int
    largest_cluster_size: int
    est_cost_usd: float
    top_clusters: list[dict]  # {cluster_id, representative, normalized_key, member_count, members}
    warnings: list[dict]  # {type, cluster_id, ...}
    size_distribution: dict[int, int]  # cluster_size -> number_of_clusters
    clustering_mode: str  # "embeddings" or "fuzzy"


def create_preview_job(
    conn: "Connection",
    *,
    file_bytes: bytes | None = None,
    text: str | None = None,
    threshold: int = 90,
    titles_per_request: int = 25,
    row_subset_mode: str = "all",
    row_subset_n: int | None = None,
    canonical_titles: list[str] | None = None,
) -> PreviewResult:
    """Create a preview job by ingesting, clustering, and persisting data.

    Args:
        conn: Database connection
        file_bytes: Raw bytes of a CSV file (optional)
        text: Pasted text with one title per line (optional)
        threshold: Clustering similarity threshold (0-100)
        titles_per_request: Number of titles per Anthropic batch request
        row_subset_mode: Row subset mode ('all', 'first_n', 'random_n')
        row_subset_n: Number of rows for 'first_n' or 'random_n' modes

    Returns:
        PreviewResult with job details, cost estimate, and top clusters

    Raises:
        CSVError: If input parsing or validation fails
        ValueError: If neither file_bytes nor text is provided
    """
    # Step 1: Ingest and normalize input
    rows = ingest(file_bytes=file_bytes, text=text)
    total_input_rows = len(rows)

    # Step 2: Create job first to get job_id for deterministic subset seeding
    job_id = jobs_dao.create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=threshold,
        titles_per_request=titles_per_request,
        row_subset_mode=row_subset_mode,
        row_subset_n=row_subset_n,
    )

    # Step 3: Apply row subset if requested (uses actual job_id for seeding)
    from app.csv_io.subset import apply_row_subset

    rows = apply_row_subset(rows, row_subset_mode, row_subset_n, job_id)
    total_rows = len(rows)

    # Step 4: Compute embeddings (once) then cluster
    precomputed_uniques = None
    precomputed_embeddings = None
    if app_settings.openai_api_key:
        precomputed_uniques, precomputed_embeddings = compute_embeddings_for_rows(rows, app_settings.openai_api_key)

    cluster_results = run_clustering(
        rows, threshold,
        openai_api_key=app_settings.openai_api_key,
        canonical_titles=canonical_titles,
        precomputed_uniques=precomputed_uniques,
        precomputed_embeddings=precomputed_embeddings,
    )
    cluster_count = len(cluster_results)

    # Step 5: Bulk insert job rows and persist embeddings for future reclusters
    job_rows_dao.bulk_insert_rows(conn, job_id, rows)
    if precomputed_uniques and precomputed_embeddings is not None:
        embeddings_cache_dao.save(conn, job_id, precomputed_uniques, precomputed_embeddings)

    # Step 6: Insert clusters and assign to rows
    warnings: list[dict] = []
    largest_cluster_size = 0
    cluster_db_id_by_norm_key: dict[str, int] = {}

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
        cluster_db_id_by_norm_key[cluster.normalized_key] = cluster_db_id

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
            # Find the job_row with matching row_index (not list position)
            row_data = next((r for r in all_job_rows if r.row_index == row_idx), None)
            if row_data is not None and row_data.original == cluster.representative_original:
                rep_row_id = row_data.id
                break

        job_rows_dao.assign_cluster(conn, row_ids, cluster_db_id, rep_row_id)

    # Step 7: Compute cost estimate
    est_cost = estimate_job_cost(cluster_count, titles_per_request)

    # Step 8: Calculate exact unique rows (after dedup)
    exact_unique = len(set(normalized for _, _, normalized in rows))

    # Step 9: Update job counts
    jobs_dao.update_job_counts(
        conn,
        job_id=job_id,
        total_rows=total_rows,
        exact_unique_rows=exact_unique,
        cluster_count=cluster_count,
        est_cost_usd=est_cost,
    )

    # Step 10: Transition to 'preview' state
    transition(conn, job_id, "preview", reason="preview_created")

    # Step 11: Build top clusters (largest 10)
    sorted_clusters = sorted(cluster_results, key=lambda c: c.member_count, reverse=True)[:10]
    row_by_index = {r.row_index: r for r in all_job_rows}
    top_clusters = [
        {
            "cluster_id": cluster_db_id_by_norm_key[c.normalized_key],
            "representative": c.representative_original,
            "normalized_key": c.normalized_key,
            "member_count": c.member_count,
            "members": [row_by_index[idx].original for idx in sorted(c.member_row_indices)],
            "member_sims": [
                round(c.norm_to_sim.get(_normalize(row_by_index[idx].original), 100.0), 1)
                for idx in sorted(c.member_row_indices)
            ],
        }
        for c in sorted_clusters
    ]

    # Step 12: Build size distribution (cluster_size -> count of clusters of that size)
    size_distribution: dict[int, int] = {}
    for c in cluster_results:
        size_distribution[c.member_count] = size_distribution.get(c.member_count, 0) + 1

    return PreviewResult(
        job_id=job_id,
        total_rows=total_rows,
        total_input_rows=total_input_rows,
        selected_rows=total_rows,
        exact_unique_rows=exact_unique,
        cluster_count=cluster_count,
        largest_cluster_size=largest_cluster_size,
        est_cost_usd=est_cost,
        top_clusters=top_clusters,
        warnings=warnings,
        size_distribution=size_distribution,
        clustering_mode="embeddings" if app_settings.openai_api_key else "fuzzy",
    )


def recluster_job(
    conn: "Connection",
    job_id: str,
    threshold: int,
    canonical_titles: list[str] | None = None,
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

    # Step 5: Load cached embeddings (if available) then cluster
    precomputed_uniques = None
    precomputed_embeddings = None
    if app_settings.openai_api_key:
        cached = embeddings_cache_dao.load(conn, job_id)
        if cached:
            precomputed_uniques, precomputed_embeddings = cached

    cluster_results = run_clustering(
        rows, threshold,
        openai_api_key=app_settings.openai_api_key,
        canonical_titles=canonical_titles,
        precomputed_uniques=precomputed_uniques,
        precomputed_embeddings=precomputed_embeddings,
    )
    cluster_count = len(cluster_results)

    # Step 6: Update job's fuzzy_threshold
    conn.execute(
        "UPDATE jobs SET fuzzy_threshold = ? WHERE id = ?",
        (threshold, job_id),
    )

    # Step 7: Insert new clusters and assign to rows
    warnings: list[dict] = []
    largest_cluster_size = 0
    cluster_db_id_by_norm_key: dict[str, int] = {}

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
        cluster_db_id_by_norm_key[cluster.normalized_key] = cluster_db_id

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
            # Find the job_row with matching row_index (not list position)
            row_data = next((r for r in fresh_job_rows if r.row_index == row_idx), None)
            if row_data is not None and row_data.original == cluster.representative_original:
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
    row_by_index_fresh = {r.row_index: r for r in fresh_job_rows}
    top_clusters = [
        {
            "cluster_id": cluster_db_id_by_norm_key[c.normalized_key],
            "representative": c.representative_original,
            "normalized_key": c.normalized_key,
            "member_count": c.member_count,
            "members": [row_by_index_fresh[idx].original for idx in sorted(c.member_row_indices)],
            "member_sims": [
                round(c.norm_to_sim.get(_normalize(row_by_index_fresh[idx].original), 100.0), 1)
                for idx in sorted(c.member_row_indices)
            ],
        }
        for c in sorted_clusters
    ]

    # Step 12: Build size distribution
    size_distribution: dict[int, int] = {}
    for c in cluster_results:
        size_distribution[c.member_count] = size_distribution.get(c.member_count, 0) + 1

    # Return PreviewResult (job_id, total_rows unchanged)
    # For recluster, total_input_rows and selected_rows are the same as total_rows
    return PreviewResult(
        job_id=job_id,
        total_rows=job.total_rows,
        total_input_rows=job.total_rows,
        selected_rows=job.total_rows,
        exact_unique_rows=exact_unique,
        cluster_count=cluster_count,
        largest_cluster_size=largest_cluster_size,
        est_cost_usd=est_cost,
        top_clusters=top_clusters,
        warnings=warnings,
        size_distribution=size_distribution,
        clustering_mode="embeddings" if app_settings.openai_api_key else "fuzzy",
    )


def commit_job(
    conn: "Connection",
    client,  # AnthropicBatchClient (protocol)
    job_id: str,
    *,
    prompt_override: str | None = None,
    taxonomy: str | None = None,
    titles_per_request: int | None = None,
    is_dry_run: bool = False,
) -> None:
    """Commit a previewed job for processing by Anthropic.

    Args:
        conn: Database connection
        client: Anthropic batch client (real or fake)
        job_id: ID of the job to commit
        prompt_override: Optional custom system prompt
        taxonomy: Optional taxonomy string for categories
        titles_per_request: Number of titles per request (uses job default if None)
        is_dry_run: If True, skip Anthropic submission and generate fake responses

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

    # Step 2: Check for concurrent jobs (skip in dry-run mode)
    if not is_dry_run:
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

    # Dry-run mode: generate fake responses and complete immediately
    if is_dry_run:
        # Update is_dry_run flag on job
        conn.execute(
            "UPDATE jobs SET is_dry_run = 1 WHERE id = ?",
            (job_id,),
        )
        # Bypass state machine for dry-run mode: go directly to submitted
        jobs_dao.update_job_status(conn, job_id, "submitted")

        # Import generate_dry_run_results
        from app.anthropic.dry_run import generate_dry_run_results

        # Generate fake responses for all clusters in chunks
        for chunk_start in range(0, len(clusters), titles_per_request):
            chunk = clusters[chunk_start:chunk_start + titles_per_request]
            cluster_ids = [c.id for c in chunk]
            titles = [c.representative_original for c in chunk]

            fake = generate_dry_run_results(cluster_ids, titles)

            # Write answers to clusters
            for i, cluster in enumerate(chunk):
                clusters_dao.update_cluster_answers(
                    conn,
                    cluster.id,
                    male_es=fake.results[i].male_es,
                    female_es=fake.results[i].female_es,
                    category=fake.results[i].category,
                )

        # Import spend_log DAO
        from app.dao import spend_log as spend_log_dao

        # Record $0 spend
        spend_log_dao.insert_spend(
            conn,
            job_id=job_id,
            batch_id=None,
            usd=0.0,
            at=int(time.time()),
        )

        # Bypass state machine: go directly to completed
        jobs_dao.update_job_status(conn, job_id, "completed")
        return

    # Step 5: Build TitleInput groups of size titles_per_request
    cluster_groups: list[list[Cluster]] = []
    for i in range(0, len(clusters), titles_per_request):
        cluster_groups.append(clusters[i:i + titles_per_request])

    # Step 6: Build request params for each group, wrapped in the {custom_id, params}
    # envelope that the Anthropic batch API requires. The custom_id is what comes back
    # in results, so we use it as the batch_requests row id too.
    all_requests: list[dict] = []
    request_cluster_groups: list[tuple[str, list[int]]] = []
    system_prompt = prompt_override if prompt_override is not None else template.system_prompt
    built_system_prompt = build_system_prompt(system_prompt, template.few_shots)

    for chunk_start, group in zip(
        range(0, len(clusters), titles_per_request), cluster_groups
    ):
        # Title IDs must be positional within the chunk ("t001", "t002", ...) so the
        # poller can map response.results[i].id back to cluster_ids[i] (see
        # worker/poller.py::_on_batch_ended). Using cluster.id here was a long-
        # standing bug that left every job stuck retrying with 0 resolved.
        titles = [
            TitleInput(
                id=f"t{i + 1:03d}",
                title=cluster.representative_original,
            )
            for i, cluster in enumerate(group)
        ]
        params = build_request_params(
            titles=titles,
            system_prompt=built_system_prompt,
            taxonomy=taxonomy,
            titles_per_request=len(titles),
        )
        custom_id = f"{job_id}-r0-c{chunk_start}"
        all_requests.append({"custom_id": custom_id, "params": params})
        request_cluster_groups.append((custom_id, [c.id for c in group]))

    # Step 7: Compute estimated cost
    estimated_cost = estimate_job_cost(len(clusters), titles_per_request)

    # Step 8: Check spend cap
    cap_check = check_cap(conn, estimated_cost)
    if not cap_check.ok:
        raise SpendCapExceeded(
            f"Monthly cap ${cap_check.cap_usd} would be exceeded "
            f"(used: ${cap_check.used_usd:.2f}, estimated: ${cap_check.estimated_usd:.2f})"
        )

    # Step 9: Update is_dry_run flag on job (False for normal commits)
    conn.execute(
        "UPDATE jobs SET is_dry_run = 0 WHERE id = ?",
        (job_id,),
    )

    # Step 10: Transition to queued state before submitting
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

    # Step 12: Persist batch_requests rows with the same custom_id we sent to Anthropic,
    # so the poller can match results back to clusters.
    for custom_id, cluster_ids in request_cluster_groups:
        batch_requests_dao.insert_request(
            conn,
            id=custom_id,
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


def record_batch_cost(
    conn: "Connection",
    *,
    job_id: str,
    batch_id: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Record actual spend from Anthropic batch API response.

    Helper called by the worker after parsing batch results.

    Args:
        conn: Database connection
        job_id: Job ID
        batch_id: Batch ID
        input_tokens: Number of input tokens consumed
        output_tokens: Number of output tokens consumed

    Returns:
        The computed USD amount
    """
    from .estimator import record_actual_spend

    return record_actual_spend(
        conn,
        job_id=job_id,
        batch_id=batch_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def review_operator_prompt(api_key: str, prompt: str, few_shots: str) -> PromptReview:
    """Review an operator's prompt using Haiku.

    Thin wrapper that calls the prompt review client and handles errors gracefully.

    Args:
        api_key: Anthropic API key
        prompt: The system prompt to review
        few_shots: JSON-serialized few-shot examples

    Returns:
        PromptReview object with review results

    Raises:
        APIError: If the Anthropic API call fails
    """
    from app.anthropic.review import review_prompt

    try:
        return review_prompt(api_key, prompt, few_shots)
    except Exception as e:
        # Catch any API errors and convert to APIError
        raise APIError(
            code="prompt_review_failed",
            message=f"Failed to review prompt: {e}",
        ) from e
