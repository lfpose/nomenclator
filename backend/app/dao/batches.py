from sqlite3 import Connection
from dataclasses import dataclass


@dataclass(frozen=True)
class Batch:
    id: str
    job_id: str
    retry_round: int
    parent_batch_id: str | None
    status: str
    request_count: int
    submitted_at: int
    polled_at: int | None
    completed_at: int | None


def insert_batch(
    conn: Connection,
    *,
    id: str,
    job_id: str,
    retry_round: int,
    parent_batch_id: str | None,
    status: str,
    request_count: int,
) -> None:
    """Insert a new batch."""
    conn.execute(
        """
        INSERT INTO batches (id, job_id, retry_round, parent_batch_id, status, request_count, submitted_at)
        VALUES (?, ?, ?, ?, ?, ?, unixepoch())
        """,
        (id, job_id, retry_round, parent_batch_id, status, request_count),
    )


def get_batch(conn: Connection, batch_id: str) -> Batch | None:
    """Get a batch by ID."""
    row = conn.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()
    if row is None:
        return None
    return Batch(**dict(row))


def update_batch_status(
    conn: Connection,
    batch_id: str,
    status: str,
    polled_at: int | None = None,
    completed_at: int | None = None,
) -> None:
    """Update batch status and optional timestamps."""
    updates = ["status = ?"]
    params = [status]

    if polled_at is not None:
        updates.append("polled_at = ?")
        params.append(polled_at)

    if completed_at is not None:
        updates.append("completed_at = ?")
        params.append(completed_at)

    params.append(batch_id)

    conn.execute(
        f"UPDATE batches SET {', '.join(updates)} WHERE id = ?",
        params,
    )


def list_batches_for_job(conn: Connection, job_id: str) -> list[Batch]:
    """List all batches for a job, ordered by retry_round ASC."""
    rows = conn.execute(
        "SELECT * FROM batches WHERE job_id = ? ORDER BY retry_round ASC",
        (job_id,),
    ).fetchall()
    return [Batch(**dict(row)) for row in rows]


def list_non_terminal_batches(conn: Connection) -> list[Batch]:
    """List all batches for non-terminal jobs."""
    rows = conn.execute(
        """
        SELECT b.*
        FROM batches b
        JOIN jobs j ON b.job_id = j.id
        WHERE j.status NOT IN ('completed', 'failed', 'cancelled')
        """,
    ).fetchall()
    return [Batch(**dict(row)) for row in rows]
