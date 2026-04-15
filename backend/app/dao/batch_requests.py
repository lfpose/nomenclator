import json
from sqlite3 import Connection
from dataclasses import dataclass


@dataclass(frozen=True)
class BatchRequest:
    id: str
    batch_id: str
    cluster_ids: list[int]
    status: str
    raw_response: str | None
    error: str | None


def insert_request(
    conn: Connection,
    *,
    id: str,
    batch_id: str,
    cluster_ids: list[int],
) -> None:
    """Insert a new batch request with cluster_ids serialized as JSON."""
    conn.execute(
        """
        INSERT INTO batch_requests (id, batch_id, cluster_ids, status)
        VALUES (?, ?, ?, 'pending')
        """,
        (id, batch_id, json.dumps(cluster_ids)),
    )


def list_requests_for_batch(conn: Connection, batch_id: str) -> list[BatchRequest]:
    """List all requests for a batch, deserializing cluster_ids from JSON."""
    rows = conn.execute(
        "SELECT * FROM batch_requests WHERE batch_id = ?",
        (batch_id,),
    ).fetchall()
    result = []
    for row in rows:
        row_dict = dict(row)
        row_dict["cluster_ids"] = json.loads(row_dict["cluster_ids"])
        result.append(BatchRequest(**row_dict))
    return result


def mark_request_completed(conn: Connection, request_id: str, raw_response: str) -> None:
    """Mark a request as completed with the raw response."""
    conn.execute(
        """
        UPDATE batch_requests
        SET status = 'completed', raw_response = ?
        WHERE id = ?
        """,
        (raw_response, request_id),
    )


def mark_request_failed(
    conn: Connection,
    request_id: str,
    error: str,
    raw_response: str | None = None,
) -> None:
    """Mark a request as failed with an error and optional raw response."""
    if raw_response is not None:
        conn.execute(
            """
            UPDATE batch_requests
            SET status = 'failed', error = ?, raw_response = ?
            WHERE id = ?
            """,
            (error, raw_response, request_id),
        )
    else:
        conn.execute(
            """
            UPDATE batch_requests
            SET status = 'failed', error = ?
            WHERE id = ?
            """,
            (error, request_id),
        )


def mark_request_missing(conn: Connection, request_id: str) -> None:
    """Mark a request as missing (no response from Anthropic)."""
    conn.execute(
        "UPDATE batch_requests SET status = 'missing' WHERE id = ?",
        (request_id,),
    )


def list_pending_requests(conn: Connection, batch_id: str) -> list[BatchRequest]:
    """List all pending requests for a batch."""
    rows = conn.execute(
        "SELECT * FROM batch_requests WHERE batch_id = ? AND status = 'pending'",
        (batch_id,),
    ).fetchall()
    result = []
    for row in rows:
        row_dict = dict(row)
        row_dict["cluster_ids"] = json.loads(row_dict["cluster_ids"])
        result.append(BatchRequest(**row_dict))
    return result
