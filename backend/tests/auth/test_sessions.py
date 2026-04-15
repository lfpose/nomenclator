from app.auth.sessions import create_session, validate_session, destroy_session


def test_create_session_returns_raw_id(conn):
    raw = create_session(conn)
    assert isinstance(raw, str)
    assert len(raw) == 64
    assert all(c in "0123456789abcdef" for c in raw)


def test_validate_session_accepts_valid_cookie(conn):
    raw = create_session(conn)
    assert validate_session(conn, raw) is True


def test_validate_session_rejects_none_or_empty(conn):
    assert validate_session(conn, None) is False
    assert validate_session(conn, "") is False


def test_validate_session_rejects_unknown(conn):
    assert validate_session(conn, "0" * 64) is False
    assert validate_session(conn, "f" * 64) is False


def test_destroy_session_invalidates(conn):
    raw = create_session(conn)
    assert validate_session(conn, raw) is True
    destroy_session(conn, raw)
    assert validate_session(conn, raw) is False


def test_db_stores_hash_not_raw(conn):
    raw = create_session(conn)
    row = conn.execute("SELECT id FROM sessions").fetchone()
    assert row is not None
    stored_hash = row["id"]
    assert stored_hash != raw
    assert len(stored_hash) == 64
    assert all(c in "0123456789abcdef" for c in stored_hash)
