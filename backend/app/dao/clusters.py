from sqlite3 import Connection
from dataclasses import dataclass


@dataclass(frozen=True)
class Cluster:
    id: int
    job_id: str
    representative_original: str
    normalized_key: str
    member_count: int
    retry_count: int
    male_es: str | None
    female_es: str | None
    category: str | None
    error: str | None


def insert_cluster(
    conn: Connection,
    *,
    job_id: str,
    representative_original: str,
    normalized_key: str,
    member_count: int,
) -> int:
    """Insert a new cluster and return its ID."""
    cursor = conn.execute(
        """
        INSERT INTO clusters (job_id, representative_original, normalized_key, member_count)
        VALUES (?, ?, ?, ?)
        """,
        (job_id, representative_original, normalized_key, member_count),
    )
    return cursor.lastrowid


def delete_clusters_for_job(conn: Connection, job_id: str) -> None:
    """Delete all clusters for a job."""
    conn.execute("DELETE FROM clusters WHERE job_id = ?", (job_id,))


def update_cluster_answers(
    conn: Connection,
    cluster_id: int,
    male_es: str,
    female_es: str,
    category: str,
) -> None:
    """Update a cluster with its answers."""
    conn.execute(
        """
        UPDATE clusters
        SET male_es = ?, female_es = ?, category = ?
        WHERE id = ?
        """,
        (male_es, female_es, category, cluster_id),
    )


def mark_cluster_error(conn: Connection, cluster_id: int, error_code: str) -> None:
    """Mark a cluster as errored with an error code."""
    conn.execute(
        "UPDATE clusters SET error = ? WHERE id = ?",
        (error_code, cluster_id),
    )


def list_clusters(conn: Connection, job_id: str) -> list[Cluster]:
    """List all clusters for a job."""
    rows = conn.execute(
        "SELECT * FROM clusters WHERE job_id = ? ORDER BY id",
        (job_id,),
    ).fetchall()
    return [Cluster(**dict(row)) for row in rows]


def count_unresolved_clusters(conn: Connection, job_id: str) -> int:
    """Count clusters that have no answers or error yet."""
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM clusters
        WHERE job_id = ?
          AND male_es IS NULL
          AND female_es IS NULL
          AND category IS NULL
          AND error IS NULL
        """,
        (job_id,),
    ).fetchone()
    return row[0]
