import time
from sqlite3 import Connection
from dataclasses import dataclass


@dataclass(frozen=True)
class SpendLog:
    id: int
    job_id: str
    batch_id: str | None
    usd: float
    at: int


def insert_spend(
    conn: Connection,
    *,
    job_id: str,
    batch_id: str | None,
    usd: float,
    at: int,
) -> None:
    """Insert a new spend log entry."""
    conn.execute(
        """
        INSERT INTO spend_log (job_id, batch_id, usd, at)
        VALUES (?, ?, ?, ?)
        """,
        (job_id, batch_id, usd, at),
    )


def sum_last_30_days(conn: Connection, now: int | None = None) -> float:
    """Sum all spend entries in the last 30 days."""
    if now is None:
        now = int(time.time())

    cutoff = now - (30 * 86400)  # 30 days in seconds

    row = conn.execute(
        "SELECT COALESCE(SUM(usd), 0) FROM spend_log WHERE at > ?",
        (cutoff,),
    ).fetchone()

    return float(row[0])


def reset_date_approx(conn: Connection, now: int | None = None) -> int | None:
    """
    Return the approximate reset date (oldest entry + 30 days).
    Returns None if there are no spend entries in the window.
    """
    if now is None:
        now = int(time.time())

    cutoff = now - (30 * 86400)  # 30 days in seconds

    row = conn.execute(
        "SELECT MIN(at) FROM spend_log WHERE at > ?",
        (cutoff,),
    ).fetchone()

    if row[0] is None:
        return None

    return row[0] + (30 * 86400)
