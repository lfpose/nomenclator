"""Tests for GET /spend endpoint."""

import tempfile

import app.settings


def get_authenticated_client(tmpdir: str, test_ip: str = "127.0.0.1"):
    """Helper to create an authenticated TestClient with a temp database."""
    db_path = f"{tmpdir}/test.db"

    # Monkeypatch settings to use temp database
    original_db_path = app.settings.settings.database_path
    app.settings.settings.database_path = db_path

    try:
        # Initialize database
        from app.db import get_connection

        conn = get_connection()
        conn.close()

        # Monkeypatch the password hash
        from app.auth.passwords import hash_password
        from app.auth import config

        correct_password = "test_password"
        correct_hash = hash_password(correct_password)

        original_hash = config.settings.auth_password_hash
        config.settings.auth_password_hash = correct_hash

        try:
            # Create a new client that uses the temp database
            from fastapi.testclient import TestClient

            from app.main import create_app

            test_client = TestClient(create_app())

            # Log in to get a session cookie
            auth_response = test_client.post(
                "/auth", json={"password": correct_password}, headers={"X-Forwarded-For": test_ip}
            )
            assert auth_response.status_code == 200
            sid = auth_response.cookies.get("sid")
            assert sid is not None

            return test_client, sid, original_hash, original_db_path
        except:
            # Restore hash on error
            config.settings.auth_password_hash = original_hash
            raise
    except:
        # Restore db path on error
        app.settings.settings.database_path = original_db_path
        raise


def cleanup_authenticated_client(test_client, sid, original_hash=None, original_db_path=None):
    """Clean up authenticated session."""
    if sid:
        test_client.post("/auth/logout", cookies={"sid": sid})
    if original_hash is not None:
        from app.auth import config
        config.settings.auth_password_hash = original_hash
    if original_db_path is not None:
        app.settings.settings.database_path = original_db_path


def test_spend_empty_returns_zero():
    """Verify spend returns zero when no entries exist."""
    test_ip = "127.0.0.1"
    with tempfile.TemporaryDirectory() as tmpdir:
        test_client, sid, original_hash, original_db_path = get_authenticated_client(tmpdir, test_ip)

        try:
            response = test_client.get("/spend", cookies={"sid": sid})
            assert response.status_code == 200
            data = response.json()
            assert data["used_usd"] == 0.0
            assert data["cap_usd"] == 20.0
            assert data["window_days"] == 30
            assert data["reset_date"] is None
        finally:
            cleanup_authenticated_client(test_client, sid, original_hash, original_db_path)


def test_spend_after_entries_returns_sum():
    """Verify spend returns sum of entries in 30-day window."""
    test_ip = "127.0.0.2"
    with tempfile.TemporaryDirectory() as tmpdir:
        test_client, sid, original_hash, original_db_path = get_authenticated_client(tmpdir, test_ip)

        try:
            # Get database path and create some spend entries
            db_path = app.settings.settings.database_path
            import sqlite3
            import time

            conn = sqlite3.connect(db_path)

            # Create a job first (required by FK constraint)
            current_time = int(time.time())
            conn.execute(
                "INSERT INTO jobs (id, status, total_rows, task_template_id, created_at) VALUES (?, ?, ?, ?, ?)",
                ("job-1", "completed", 1, "job_titles_es", current_time),
            )

            # Insert spend entries totaling $5.00 (within 30-day window)
            conn.execute(
                "INSERT INTO spend_log (job_id, usd, at) VALUES (?, ?, ?)",
                ("job-1", 2.5, current_time),
            )
            conn.execute(
                "INSERT INTO spend_log (job_id, usd, at) VALUES (?, ?, ?)",
                ("job-1", 2.5, current_time + 10),
            )
            conn.commit()
            conn.close()

            response = test_client.get("/spend", cookies={"sid": sid})
            assert response.status_code == 200
            data = response.json()
            assert data["used_usd"] == 5.0
            assert data["cap_usd"] == 20.0
            assert data["window_days"] == 30
        finally:
            cleanup_authenticated_client(test_client, sid, original_hash, original_db_path)


def test_spend_reset_date_when_entries_exist():
    """Verify reset_date is returned when entries exist."""
    import time

    test_ip = "127.0.0.3"
    with tempfile.TemporaryDirectory() as tmpdir:
        test_client, sid, original_hash, original_db_path = get_authenticated_client(tmpdir, test_ip)

        try:
            db_path = app.settings.settings.database_path
            import sqlite3

            conn = sqlite3.connect(db_path)

            # Create a job
            conn.execute(
                "INSERT INTO jobs (id, status, total_rows, task_template_id, created_at) VALUES (?, ?, ?, ?, ?)",
                ("job-1", "completed", 1, "job_titles_es", 1234567890),
            )

            # Insert a spend entry with a known timestamp
            entry_time = int(time.time())
            conn.execute(
                "INSERT INTO spend_log (job_id, usd, at) VALUES (?, ?, ?)",
                ("job-1", 1.0, entry_time),
            )
            conn.commit()
            conn.close()

            response = test_client.get("/spend", cookies={"sid": sid})
            assert response.status_code == 200
            data = response.json()
            assert data["used_usd"] == 1.0
            assert data["cap_usd"] == 20.0
            assert data["reset_date"] is not None

            # Verify reset date is approximately 30 days from entry
            from datetime import datetime, timedelta

            reset_date = datetime.fromisoformat(data["reset_date"])
            entry_date = datetime.fromtimestamp(entry_time)
            expected_reset = entry_date + timedelta(days=30)
            
            # Allow for small time differences
            assert abs((reset_date - expected_reset).days) <= 1
        finally:
            cleanup_authenticated_client(test_client, sid, original_hash, original_db_path)
