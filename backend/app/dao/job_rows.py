from sqlite3 import Connection
from dataclasses import dataclass


@dataclass(frozen=True)
class JobRow:
    id: int
    job_id: str
    cluster_id: int | None
    row_index: int
    original: str
    normalized: str
    is_representative: bool


def bulk_insert_rows(conn: Connection, job_id: str, rows: list[tuple[int, str, str]]) -> None:
    """Bulk insert job rows. Each tuple is (row_index, original, normalized)."""
    conn.executemany(
        "INSERT INTO job_rows (job_id, row_index, original, normalized) VALUES (?, ?, ?, ?)",
        [(job_id, row_index, original, normalized) for row_index, original, normalized in rows],
    )


def list_rows(conn: Connection, job_id: str) -> list[JobRow]:
    """List all rows for a job, ordered by row_index."""
    cursor = conn.execute(
        "SELECT id, job_id, cluster_id, row_index, original, normalized, is_representative "
        "FROM job_rows WHERE job_id = ? ORDER BY row_index",
        (job_id,),
    )
    return [
        JobRow(
            id=row["id"],
            job_id=row["job_id"],
            cluster_id=row["cluster_id"],
            row_index=row["row_index"],
            original=row["original"],
            normalized=row["normalized"],
            is_representative=bool(row["is_representative"]),
        )
        for row in cursor.fetchall()
    ]


def assign_cluster(
    conn: Connection,
    row_ids: list[int],
    cluster_id: int,
    is_representative_row_id: int | None,
) -> None:
    """Bulk assign a cluster to rows. Mark the representative row if specified."""
    # First, clear is_representative for all rows being assigned
    if row_ids:
        conn.execute(
            "UPDATE job_rows SET is_representative = 0 WHERE id IN ({})".format(
                ",".join("?" * len(row_ids))
            ),
            row_ids,
        )

    # Update cluster_id for all rows
    if row_ids:
        conn.execute(
            "UPDATE job_rows SET cluster_id = ? WHERE id IN ({})".format(
                ",".join("?" * len(row_ids))
            ),
            [cluster_id] + row_ids,
        )

    # Mark the representative row
    if is_representative_row_id is not None:
        conn.execute(
            "UPDATE job_rows SET is_representative = 1 WHERE id = ?",
            (is_representative_row_id,),
        )


def clear_clusters(conn: Connection, job_id: str) -> None:
    """Clear cluster assignments for all rows in a job."""
    conn.execute(
        "UPDATE job_rows SET cluster_id = NULL, is_representative = 0 WHERE job_id = ?",
        (job_id,),
    )
