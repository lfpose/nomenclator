"""Tests for failed-job transition on row count drift."""

import sqlite3
import tempfile

import app.settings
from tests.anthropic.fake_client import FakeAnthropicBatchClient


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

            fastapi_app = create_app()
            # Override with fake client for testing
            fake_client = FakeAnthropicBatchClient()
            fastapi_app.state.anthropic_client = fake_client

            test_client = TestClient(fastapi_app)

            # Log in to get a session cookie
            auth_response = test_client.post(
                "/auth", json={"password": correct_password}, headers={"X-Forwarded-For": test_ip}
            )
            assert auth_response.status_code == 200
            sid = auth_response.cookies.get("sid")
            assert sid is not None

            return test_client, sid, original_hash
        except:
            # Restore hash on error
            config.settings.auth_password_hash = original_hash
            raise
    except:
        # Restore db path on error
        app.settings.settings.database_path = original_db_path
        raise


def cleanup_authenticated_client(test_client, sid):
    """Clean up authenticated session."""
    if sid:
        test_client.post("/auth/logout", cookies={"sid": sid})


def test_download_drift_transitions_job_to_failed():
    """Verifies job transitions to failed state on row count drift."""
    test_ip = "127.0.0.1"
    with tempfile.TemporaryDirectory() as tmpdir:
        test_client, sid, original_hash = get_authenticated_client(tmpdir, test_ip)

        try:
            # Get database path from settings
            db_path = app.settings.settings.database_path

            # Create and commit a job via API
            preview_response = test_client.post(
                "/jobs/preview",
                data={"threshold": 90, "titles_per_request": 25, "text": "Jefe de Compras\nIngeniero de Ventas"},
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )
            assert preview_response.status_code == 200
            job_id = preview_response.json()["job_id"]

            commit_response = test_client.post(
                f"/jobs/{job_id}/commit",
                json={"is_dry_run": True},
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )
            assert commit_response.status_code == 202

            # Manually cause drift by deleting a job row (simulating data corruption)
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("DELETE FROM job_rows WHERE job_id = ? LIMIT 1", (job_id,))
            conn.commit()
            conn.close()

            # Try to download - should detect drift and transition to failed
            download_response = test_client.get(f"/jobs/{job_id}/download", cookies={"sid": sid})
            assert download_response.status_code == 500

            # Verify job is now in failed state
            job_response = test_client.get(f"/jobs/{job_id}", cookies={"sid": sid})
            assert job_response.status_code == 200
            job_data = job_response.json()
            assert job_data["status"] == "failed"
        finally:
            cleanup_authenticated_client(test_client, sid)


def test_download_drift_returns_500():
    """Verifies drift returns 500 internal error."""
    test_ip = "127.0.0.2"
    with tempfile.TemporaryDirectory() as tmpdir:
        test_client, sid, original_hash = get_authenticated_client(tmpdir, test_ip)

        try:
            db_path = app.settings.settings.database_path

            # Create and commit a job
            preview_response = test_client.post(
                "/jobs/preview",
                data={"threshold": 90, "titles_per_request": 25, "text": "Jefe de Compras"},
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )
            assert preview_response.status_code == 200
            job_id = preview_response.json()["job_id"]

            commit_response = test_client.post(
                f"/jobs/{job_id}/commit",
                json={"is_dry_run": True},
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )
            assert commit_response.status_code == 202

            # Manually cause drift by deleting a job row
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("DELETE FROM job_rows WHERE job_id = ? LIMIT 1", (job_id,))
            conn.commit()
            conn.close()

            # Try to download
            download_response = test_client.get(f"/jobs/{job_id}/download", cookies={"sid": sid})
            assert download_response.status_code == 500

            # Verify error response
            data = download_response.json()
            assert data["error"]["code"] == "internal_error"
            assert "drift" in data["error"]["message"].lower()
        finally:
            cleanup_authenticated_client(test_client, sid)


def test_download_drift_never_returns_csv_bytes():
    """Verifies drift never returns CSV bytes (always returns error JSON)."""
    test_ip = "127.0.0.3"
    with tempfile.TemporaryDirectory() as tmpdir:
        test_client, sid, original_hash = get_authenticated_client(tmpdir, test_ip)

        try:
            db_path = app.settings.settings.database_path

            # Create and commit a job
            preview_response = test_client.post(
                "/jobs/preview",
                data={"threshold": 90, "titles_per_request": 25, "text": "Jefe de Compras"},
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )
            assert preview_response.status_code == 200
            job_id = preview_response.json()["job_id"]

            commit_response = test_client.post(
                f"/jobs/{job_id}/commit",
                json={"is_dry_run": True},
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )
            assert commit_response.status_code == 202

            # Manually cause drift by deleting all job rows
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("DELETE FROM job_rows WHERE job_id = ?", (job_id,))
            conn.commit()
            conn.close()

            # Try to download
            download_response = test_client.get(f"/jobs/{job_id}/download", cookies={"sid": sid})
            assert download_response.status_code == 500

            # Verify response is JSON, not CSV bytes
            content_type = download_response.headers.get("content-type", "")
            assert "application/json" in content_type or "text/csv" not in content_type

            # Verify it's parseable JSON
            data = download_response.json()
            assert "error" in data
            assert data["error"]["code"] == "internal_error"

            # Verify it's not CSV content (no BOM, no header row)
            content = download_response.content
            assert not content.startswith(b"\xef\xbb\xbf")  # No BOM
            assert b"original,male_es,female_es,category,error" not in content  # No CSV header
        finally:
            cleanup_authenticated_client(test_client, sid)
