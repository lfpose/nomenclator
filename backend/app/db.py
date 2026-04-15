import sqlite3
from pathlib import Path
from typing import Generator

from .settings import settings

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def get_connection() -> sqlite3.Connection:
    """Create a SQLite connection with WAL mode, foreign keys, and apply migrations."""
    # For file-based databases, disable thread check to allow TestClient to work
    # (TestClient runs requests in a separate thread)
    check_same_thread = settings.database_path == ":memory:"
    conn = sqlite3.connect(settings.database_path, isolation_level=None, check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    _apply_migrations(conn)
    return conn


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply any pending migrations from the migrations directory."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at INTEGER NOT NULL
        )
    """
    )
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_version")}
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = int(path.name.split("_")[0])
        if version in applied:
            continue
        sql = path.read_text()
        conn.executescript(sql)
        conn.execute("INSERT INTO schema_version VALUES (?, unixepoch())", (version,))


def db_dep() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency that yields a per-request SQLite connection and closes it on teardown."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
