import hashlib
import time
import pytest

from app.dao.sessions import Session, create_session, delete_session, get_valid_session, purge_expired


def test_create_and_get_roundtrips(conn):
    """Test that create_session and get_valid_session roundtrip correctly."""
    raw_token = "0123456789abcdef" * 4  # 64 hex chars = 256 bits
    session_id_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    create_session(conn, session_id_hash=session_id_hash, ttl_seconds=3600)

    session = get_valid_session(conn, session_id_hash=session_id_hash)
    assert session is not None
    assert session.id == session_id_hash
    assert session.created_at is not None
    assert session.expires_at is not None
    assert session.expires_at > session.created_at


def test_get_valid_session_returns_none_if_expired(conn):
    """Test that get_valid_session returns None for expired sessions."""
    raw_token = "fedcba9876543210" * 4
    session_id_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    # Create session that expires in 1 second
    create_session(conn, session_id_hash=session_id_hash, ttl_seconds=1)

    # Should be valid immediately
    assert get_valid_session(conn, session_id_hash=session_id_hash) is not None

    # Travel forward 2 seconds
    future_time = int(time.time()) + 2
    assert get_valid_session(conn, session_id_hash=session_id_hash, now=future_time) is None


def test_delete_session_removes_row(conn):
    """Test that delete_session removes the session row."""
    raw_token = "deadbeefcafe1234" * 4
    session_id_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    create_session(conn, session_id_hash=session_id_hash)
    assert get_valid_session(conn, session_id_hash=session_id_hash) is not None

    delete_session(conn, session_id_hash=session_id_hash)
    assert get_valid_session(conn, session_id_hash=session_id_hash) is None


def test_purge_expired_counts_and_removes(conn):
    """Test that purge_expired removes expired sessions and returns count."""
    base_time = int(time.time())

    # Create sessions with different TTLs
    create_session(conn, session_id_hash="expired-1", ttl_seconds=100)
    create_session(conn, session_id_hash="expired-2", ttl_seconds=200)
    create_session(conn, session_id_hash="valid-1", ttl_seconds=1000)
    create_session(conn, session_id_hash="valid-2", ttl_seconds=2000)

    # Purge as if we're 300 seconds in the future
    # This should remove expired-1 and expired-2 (100 and 200 second TTL)
    purged_count = purge_expired(conn, now=base_time + 300)
    assert purged_count == 2

    # Verify expired sessions are gone
    assert get_valid_session(conn, session_id_hash="expired-1", now=base_time + 300) is None
    assert get_valid_session(conn, session_id_hash="expired-2", now=base_time + 300) is None

    # Verify valid sessions still exist
    assert get_valid_session(conn, session_id_hash="valid-1", now=base_time + 300) is not None
    assert get_valid_session(conn, session_id_hash="valid-2", now=base_time + 300) is not None


def test_hash_not_raw_stored(conn):
    """Verify that only the hash is stored in the database, not the raw token."""
    raw_token = "secret1234567890" * 4  # Simulated raw session token
    raw_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    # Create session with hash only
    create_session(conn, session_id_hash=raw_hash, ttl_seconds=3600)

    # Verify the stored value is the hash, not the raw token
    stored_id = conn.execute(
        "SELECT id FROM sessions WHERE id = ?", (raw_hash,)
    ).fetchone()
    assert stored_id is not None
    assert stored_id["id"] == raw_hash

    # Verify raw token cannot be used to retrieve the session
    session_via_raw = get_valid_session(conn, session_id_hash=raw_token)
    assert session_via_raw is None

    # Verify only the hash works
    session_via_hash = get_valid_session(conn, session_id_hash=raw_hash)
    assert session_via_hash is not None
