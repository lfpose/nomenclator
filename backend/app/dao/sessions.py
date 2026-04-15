import time
from dataclasses import dataclass

from sqlite3 import Connection


@dataclass(frozen=True)
class Session:
    id: str  # sha256 hash of the raw session token
    created_at: int
    expires_at: int


def create_session(conn: Connection, *, session_id_hash: str, ttl_seconds: int = 2592000) -> None:
    """Create a new session. session_id_hash is the SHA-256 hash of the raw token."""
    now = int(time.time())
    expires_at = now + ttl_seconds
    conn.execute(
        "INSERT INTO sessions (id, created_at, expires_at) VALUES (?, ?, ?)",
        (session_id_hash, now, expires_at),
    )


def get_valid_session(
    conn: Connection, session_id_hash: str, now: int | None = None
) -> Session | None:
    """Get a session by its ID hash, returning None if expired."""
    if now is None:
        now = int(time.time())
    row = conn.execute(
        "SELECT * FROM sessions WHERE id = ? AND expires_at > ?",
        (session_id_hash, now),
    ).fetchone()
    if row is None:
        return None
    return Session(id=row["id"], created_at=row["created_at"], expires_at=row["expires_at"])


def delete_session(conn: Connection, session_id_hash: str) -> None:
    """Delete a session by its ID hash."""
    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id_hash,))


def purge_expired(conn: Connection, now: int | None = None) -> int:
    """Delete all expired sessions and return the count of deleted rows."""
    if now is None:
        now = int(time.time())
    cursor = conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
    return cursor.rowcount
