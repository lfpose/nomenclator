"""Tests for GET /jobs/:id/download endpoint."""

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


def test_download_completed_job_returns_csv():
    """Verifies download returns CSV for a completed job."""
    test_ip = "127.0.0.1"
    with tempfile.TemporaryDirectory() as tmpdir:
        test_client, sid, original_hash = get_authenticated_client(tmpdir, test_ip)

        try:
            # Create a preview job
            preview_response = test_client.post(
                "/jobs/preview",
                data={
                    "threshold": 90,
                    "titles_per_request": 25,
                    "text": "Jefe de Compras\nIngeniero de Ventas\nGerente de Marketing",
                },
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )
            assert preview_response.status_code == 200
            job_id = preview_response.json()["job_id"]

            # Commit the job in dry-run mode (bypasses Anthropic API)
            commit_response = test_client.post(
                f"/jobs/{job_id}/commit",
                json={"is_dry_run": True},
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )
            assert commit_response.status_code == 202

            # Download the job
            download_response = test_client.get(f"/jobs/{job_id}/download", cookies={"sid": sid})
            assert download_response.status_code == 200

            # Check content type
            assert "text/csv" in download_response.headers.get("content-type", "")

            # Check content disposition
            content_disposition = download_response.headers.get("content-disposition", "")
            assert "attachment" in content_disposition
            assert "nomenclator-" in content_disposition
            assert ".csv" in content_disposition

            # Check CSV content
            content = download_response.content
            assert content.startswith(b"\xef\xbb\xbf")  # BOM
            content_str = content[3:].decode("utf-8")
            assert "original,male_es,female_es,category,error" in content_str
            assert "Jefe de Compras" in content_str
            assert "Ingeniero de Ventas" in content_str
            assert "Gerente de Marketing" in content_str
        finally:
            cleanup_authenticated_client(test_client, sid)


def test_download_starts_with_utf8_bom():
    """Verifies download starts with UTF-8 BOM."""
    test_ip = "127.0.0.2"
    with tempfile.TemporaryDirectory() as tmpdir:
        test_client, sid, original_hash = get_authenticated_client(tmpdir, test_ip)

        try:
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

            download_response = test_client.get(f"/jobs/{job_id}/download", cookies={"sid": sid})
            assert download_response.status_code == 200
            assert download_response.content.startswith(b"\xef\xbb\xbf")
        finally:
            cleanup_authenticated_client(test_client, sid)


def test_download_filename_header_set():
    """Verifies filename is set correctly in Content-Disposition header."""
    test_ip = "127.0.0.3"
    with tempfile.TemporaryDirectory() as tmpdir:
        test_client, sid, original_hash = get_authenticated_client(tmpdir, test_ip)

        try:
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

            download_response = test_client.get(f"/jobs/{job_id}/download", cookies={"sid": sid})
            assert download_response.status_code == 200
            content_disposition = download_response.headers.get("content-disposition", "")
            # Should start with "nomenclator-" and end with ".csv"
            assert "nomenclator-" in content_disposition
            assert ".csv" in content_disposition
            # Should contain the first 8 chars of the job ID
            job_id_short = job_id.replace("-", "")[:8]
            assert job_id_short in content_disposition
        finally:
            cleanup_authenticated_client(test_client, sid)


def test_download_non_completed_returns_409():
    """Verifies download returns 409 for non-completed jobs."""
    test_ip = "127.0.0.4"
    with tempfile.TemporaryDirectory() as tmpdir:
        test_client, sid, original_hash = get_authenticated_client(tmpdir, test_ip)

        try:
            # Create a preview job (not committed)
            preview_response = test_client.post(
                "/jobs/preview",
                data={"threshold": 90, "titles_per_request": 25, "text": "Jefe de Compras"},
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )
            assert preview_response.status_code == 200
            job_id = preview_response.json()["job_id"]

            # Try to download the preview job
            download_response = test_client.get(f"/jobs/{job_id}/download", cookies={"sid": sid})
            assert download_response.status_code == 409
            data = download_response.json()
            assert data["error"]["code"] == "invalid_state"
        finally:
            cleanup_authenticated_client(test_client, sid)


def test_download_missing_404():
    """Verifies download returns 404 for missing job."""
    test_ip = "127.0.0.5"
    with tempfile.TemporaryDirectory() as tmpdir:
        test_client, sid, original_hash = get_authenticated_client(tmpdir, test_ip)

        try:
            # Try to download a non-existent job
            download_response = test_client.get(
                f"/jobs/00000000-0000-0000-0000-000000000000/download",
                cookies={"sid": sid},
            )
            assert download_response.status_code == 404
            data = download_response.json()
            assert data["error"]["code"] == "job_not_found"
        finally:
            cleanup_authenticated_client(test_client, sid)
