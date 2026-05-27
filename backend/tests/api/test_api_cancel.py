"""Tests for POST /jobs/:id/cancel endpoint."""

import tempfile

from app.auth.passwords import hash_password
from app.dao import jobs as jobs_dao


def get_authenticated_client(tmpdir: str, test_ip: str = "127.0.0.1"):
    """Helper to create an authenticated TestClient with a temp database."""
    db_path = f"{tmpdir}/test.db"

    # Monkeypatch settings to use temp database
    import app.settings

    original_db_path = app.settings.settings.database_path
    app.settings.settings.database_path = db_path

    try:
        # Initialize database
        from app.db import get_connection

        conn = get_connection()
        conn.close()

        # Monkeypatch the password hash
        correct_password = "test_password"
        correct_hash = hash_password(correct_password)

        import app.auth.config

        original_hash = app.auth.config.settings.auth_password_hash
        app.auth.config.settings.auth_password_hash = correct_hash

        try:
            # Create a new client that uses the temp database
            from fastapi.testclient import TestClient

            from app.main import create_app

            app = create_app()
            # Override with fake client for testing
            from tests.anthropic.fake_client import FakeAnthropicBatchClient

            fake_client = FakeAnthropicBatchClient()
            app.state.anthropic_client = fake_client

            test_client = TestClient(app)

            # Log in to get a session cookie with unique IP
            auth_response = test_client.post(
                "/auth", json={"password": correct_password}, headers={"X-Forwarded-For": test_ip}
            )
            assert auth_response.status_code == 200

            sid = auth_response.cookies.get("sid")
            assert sid is not None

            return test_client, sid, original_hash, original_db_path
        except:
            # Restore hash on error
            app.auth.config.settings.auth_password_hash = original_hash
            raise
    except:
        # Restore db path on error
        app.settings.settings.database_path = original_db_path
        raise


def cleanup_authenticated_client(original_hash: str, original_db_path: str):
    """Helper to clean up after get_authenticated_client."""
    import app.auth.config
    import app.settings

    app.auth.config.settings.auth_password_hash = original_hash
    app.settings.settings.database_path = original_db_path


def get_conn(tmpdir: str):
    """Get a connection to the test database."""
    from app.db import get_connection

    db_path = f"{tmpdir}/test.db"

    import app.settings

    original_db_path = app.settings.settings.database_path
    app.settings.settings.database_path = db_path
    try:
        return get_connection()
    finally:
        app.settings.settings.database_path = original_db_path


def test_cancel_transitions_to_cancelled():
    """Cancel endpoint should transition job to cancelled state."""
    test_ip = "127.0.0.1"
    with tempfile.TemporaryDirectory() as tmpdir:
        test_client, sid, original_hash, original_db_path = get_authenticated_client(tmpdir, test_ip)

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

            # Manually set job to queued state (cancellable)
            conn = get_conn(tmpdir)
            jobs_dao.update_job_status(conn, job_id, "queued")
            conn.close()

            # Cancel the job
            cancel_response = test_client.post(
                f"/jobs/{job_id}/cancel",
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )
            assert cancel_response.status_code == 200
            data = cancel_response.json()
            assert data["ok"] is True

            # Verify job is in cancelled state
            conn = get_conn(tmpdir)
            job = jobs_dao.get_job(conn, job_id)
            conn.close()
            assert job.status == "cancelled"
        finally:
            cleanup_authenticated_client(original_hash, original_db_path)


def test_cancel_terminal_returns_409():
    """Cancel endpoint should return 409 when job is in a terminal state."""
    test_ip = "127.0.0.2"
    with tempfile.TemporaryDirectory() as tmpdir:
        test_client, sid, original_hash, original_db_path = get_authenticated_client(tmpdir, test_ip)

        try:
            # Create a job and manually set it to completed state
            conn = get_conn(tmpdir)
            job_id = jobs_dao.create_job(
                conn,
                task_template_id="job_titles_es",
                fuzzy_threshold=90,
                titles_per_request=25,
            )
            jobs_dao.update_job_status(conn, job_id, "completed")
            conn.close()

            # Try to cancel a completed job
            cancel_response = test_client.post(
                f"/jobs/{job_id}/cancel",
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )
            assert cancel_response.status_code == 409
            data = cancel_response.json()
            assert data["error"]["code"] == "invalid_state"
        finally:
            cleanup_authenticated_client(original_hash, original_db_path)


def test_cancel_missing_job_404():
    """Cancel endpoint should return 404 when job does not exist."""
    test_ip = "127.0.0.3"
    with tempfile.TemporaryDirectory() as tmpdir:
        test_client, sid, original_hash, original_db_path = get_authenticated_client(tmpdir, test_ip)

        try:
            # Try to cancel a non-existent job
            cancel_response = test_client.post(
                "/jobs/nonexistent-job-id/cancel",
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )
            assert cancel_response.status_code == 404
            data = cancel_response.json()
            assert data["error"]["code"] == "job_not_found"
        finally:
            cleanup_authenticated_client(original_hash, original_db_path)
