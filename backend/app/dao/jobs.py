import uuid

from sqlite3 import Connection
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Self


@dataclass(frozen=True)
class Job:
    id: str
    task_template_id: str
    status: str
    user_prompt_override: str | None
    user_taxonomy: str | None
    fuzzy_threshold: int
    titles_per_request: int
    row_subset_mode: str
    row_subset_n: int | None
    is_dry_run: bool
    total_rows: int
    exact_unique_rows: int
    cluster_count: int
    completed_rows: int
    error_rows: int
    est_cost_usd: float
    actual_cost_usd: float
    created_at: int
    finished_at: int | None


def create_job(
    conn: Connection,
    *,
    task_template_id: str,
    fuzzy_threshold: int,
    titles_per_request: int,
    row_subset_mode: str = "all",
    row_subset_n: int | None = None,
    is_dry_run: bool = False,
) -> str:
    """Create a new job and return its UUID."""
    job_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO jobs (
            id, task_template_id, status, fuzzy_threshold, titles_per_request,
            row_subset_mode, row_subset_n, is_dry_run, created_at
        ) VALUES (?, ?, 'draft', ?, ?, ?, ?, ?, unixepoch())
        """,
        (
            job_id,
            task_template_id,
            fuzzy_threshold,
            titles_per_request,
            row_subset_mode,
            row_subset_n,
            1 if is_dry_run else 0,
        ),
    )
    return job_id


def get_job(conn: Connection, job_id: str) -> Job | None:
    """Fetch a job by ID, or None if not found."""
    row = conn.execute(
        "SELECT * FROM jobs WHERE id = ?",
        (job_id,)
    ).fetchone()
    if row is None:
        return None
    return Job(
        id=row["id"],
        task_template_id=row["task_template_id"],
        status=row["status"],
        user_prompt_override=row["user_prompt_override"],
        user_taxonomy=row["user_taxonomy"],
        fuzzy_threshold=row["fuzzy_threshold"],
        titles_per_request=row["titles_per_request"],
        row_subset_mode=row["row_subset_mode"],
        row_subset_n=row["row_subset_n"],
        is_dry_run=row["is_dry_run"] == 1,
        total_rows=row["total_rows"],
        exact_unique_rows=row["exact_unique_rows"],
        cluster_count=row["cluster_count"],
        completed_rows=row["completed_rows"],
        error_rows=row["error_rows"],
        est_cost_usd=row["est_cost_usd"],
        actual_cost_usd=row["actual_cost_usd"],
        created_at=row["created_at"],
        finished_at=row["finished_at"],
    )


def list_jobs(conn: Connection) -> list[Job]:
    """List all jobs ordered by created_at DESC."""
    rows = conn.execute(
        "SELECT * FROM jobs ORDER BY created_at DESC"
    ).fetchall()
    return [
        Job(
            id=row["id"],
            task_template_id=row["task_template_id"],
            status=row["status"],
            user_prompt_override=row["user_prompt_override"],
            user_taxonomy=row["user_taxonomy"],
            fuzzy_threshold=row["fuzzy_threshold"],
            titles_per_request=row["titles_per_request"],
            row_subset_mode=row["row_subset_mode"],
            row_subset_n=row["row_subset_n"],
            is_dry_run=row["is_dry_run"] == 1,
            total_rows=row["total_rows"],
            exact_unique_rows=row["exact_unique_rows"],
            cluster_count=row["cluster_count"],
            completed_rows=row["completed_rows"],
            error_rows=row["error_rows"],
            est_cost_usd=row["est_cost_usd"],
            actual_cost_usd=row["actual_cost_usd"],
            created_at=row["created_at"],
            finished_at=row["finished_at"],
        )
        for row in rows
    ]


def update_job_status(conn: Connection, job_id: str, new_status: str) -> None:
    """Update the status of a job."""
    conn.execute(
        "UPDATE jobs SET status = ? WHERE id = ?",
        (new_status, job_id),
    )


def update_job_counts(conn: Connection, job_id: str, **counts) -> None:
    """Update count fields on a job."""
    valid_fields = {
        "total_rows",
        "exact_unique_rows",
        "cluster_count",
        "completed_rows",
        "error_rows",
        "est_cost_usd",
        "actual_cost_usd",
        "finished_at",
    }
    
    # Filter to only valid fields that were provided
    updates = {k: v for k, v in counts.items() if k in valid_fields and v is not None}
    
    if not updates:
        return
    
    # Build the SET clause
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [job_id]
    
    conn.execute(
        f"UPDATE jobs SET {set_clause} WHERE id = ?",
        values,
    )


def count_active_jobs(conn: Connection) -> int:
    """Count jobs in non-terminal states."""
    result = conn.execute(
        """
        SELECT COUNT(*) FROM jobs
        WHERE status IN ('queued', 'submitted', 'polling', 'retrying')
    """
    ).fetchone()
    return result[0]
