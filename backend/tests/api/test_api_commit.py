"""Tests for POST /jobs/:id/commit endpoint."""

import tempfile
import time

from app.auth.passwords import hash_password
from app.dao import jobs as jobs_dao
from app.dao import spend_log as spend_log_dao
from tests.anthropic.fake_client import FakeAnthropicBatchClient


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


def test_commit_happy_path_returns_202():
    """Commit endpoint should return 202 and transition job to submitted state."""
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

            # Commit the job
            commit_response = test_client.post(
                f"/jobs/{job_id}/commit",
                json={},
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )
            assert commit_response.status_code == 202
            data = commit_response.json()
            assert data["job_id"] == job_id
            assert data["status"] == "submitted"

            # Verify job is in submitted state
            conn = get_conn(tmpdir)
            job = jobs_dao.get_job(conn, job_id)
            conn.close()
            assert job.status == "submitted"
        finally:
            cleanup_authenticated_client(original_hash, original_db_path)


def test_commit_spend_cap_returns_409():
    """Commit endpoint should return 409 when spend cap is exceeded."""
    test_ip = "127.0.0.2"
    with tempfile.TemporaryDirectory() as tmpdir:
        test_client, sid, original_hash, original_db_path = get_authenticated_client(tmpdir, test_ip)

        try:
            # Pre-seed spend log to hit cap limit ($20)
            conn = get_conn(tmpdir)
            job_id_1 = jobs_dao.create_job(
                conn,
                task_template_id="job_titles_es",
                fuzzy_threshold=90,
                titles_per_request=25,
            )
            spend_log_dao.insert_spend(
                conn,
                job_id=job_id_1,
                batch_id=None,
                usd=20.0,
                at=int(time.time()),
            )
            conn.close()

            # Create a preview job
            preview_response = test_client.post(
                "/jobs/preview",
                data={
                    "threshold": 90,
                    "titles_per_request": 25,
                    "text": "Jefe de Compras\nIngeniero de Ventas",
                },
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )
            assert preview_response.status_code == 200
            job_id = preview_response.json()["job_id"]

            # Commit should fail with spend_cap_exceeded error
            commit_response = test_client.post(
                f"/jobs/{job_id}/commit",
                json={},
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )
            assert commit_response.status_code == 409
            data = commit_response.json()
            assert data["error"]["code"] == "spend_cap_exceeded"
        finally:
            cleanup_authenticated_client(original_hash, original_db_path)


def test_commit_concurrent_returns_409():
    """Commit endpoint should return 409 when another job is already running."""
    test_ip = "127.0.0.3"
    with tempfile.TemporaryDirectory() as tmpdir:
        test_client, sid, original_hash, original_db_path = get_authenticated_client(tmpdir, test_ip)

        try:
            # Create first preview job and commit it
            preview_response1 = test_client.post(
                "/jobs/preview",
                data={
                    "threshold": 90,
                    "titles_per_request": 25,
                    "text": "Jefe de Compras",
                },
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )
            assert preview_response1.status_code == 200
            job_id_1 = preview_response1.json()["job_id"]

            # Commit first job
            commit_response1 = test_client.post(
                f"/jobs/{job_id_1}/commit",
                json={},
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )
            assert commit_response1.status_code == 202

            # Create second preview job
            preview_response2 = test_client.post(
                "/jobs/preview",
                data={
                    "threshold": 90,
                    "titles_per_request": 25,
                    "text": "Ingeniero de Ventas",
                },
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )
            assert preview_response2.status_code == 200
            job_id_2 = preview_response2.json()["job_id"]

            # Commit second job should fail with job_already_running error
            commit_response2 = test_client.post(
                f"/jobs/{job_id_2}/commit",
                json={},
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )
            assert commit_response2.status_code == 409
            data = commit_response2.json()
            assert data["error"]["code"] == "job_already_running"
        finally:
            cleanup_authenticated_client(original_hash, original_db_path)


def test_commit_non_preview_returns_409():
    """Commit endpoint should return 409 when job is not in preview state."""
    test_ip = "127.0.0.4"
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

            # Try to commit a completed job
            commit_response = test_client.post(
                f"/jobs/{job_id}/commit",
                json={},
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )
            assert commit_response.status_code == 409
            data = commit_response.json()
            assert data["error"]["code"] == "invalid_state"
        finally:
            cleanup_authenticated_client(original_hash, original_db_path)


def test_commit_missing_job_returns_404():
    """Commit endpoint should return 404 when job does not exist."""
    test_ip = "127.0.0.5"
    with tempfile.TemporaryDirectory() as tmpdir:
        test_client, sid, original_hash, original_db_path = get_authenticated_client(tmpdir, test_ip)

        try:
            # Try to commit a non-existent job
            commit_response = test_client.post(
                "/jobs/nonexistent-job-id/commit",
                json={},
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )
            assert commit_response.status_code == 404
            data = commit_response.json()
            assert data["error"]["code"] == "job_not_found"
        finally:
            cleanup_authenticated_client(original_hash, original_db_path)


def test_commit_rate_limited_after_10():
    """Commit endpoint should rate limit after 10 commits per hour."""
    test_ip = "127.0.0.6"
    with tempfile.TemporaryDirectory() as tmpdir:
        test_client, sid, original_hash, original_db_path = get_authenticated_client(tmpdir, test_ip)

        try:
            # Create 10 preview jobs and commit them in dry-run mode
            # (dry-run mode skips concurrency check, allowing us to test rate limiting)
            for i in range(10):
                preview_response = test_client.post(
                    "/jobs/preview",
                    data={
                        "threshold": 90,
                        "titles_per_request": 25,
                        "text": f"Job Title {i}",
                    },
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

            # The 11th commit should be rate limited
            preview_response = test_client.post(
                "/jobs/preview",
                data={
                    "threshold": 90,
                    "titles_per_request": 25,
                    "text": "Job Title 10",
                },
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
            assert commit_response.status_code == 429
            data = commit_response.json()
            assert data["error"]["code"] == "rate_limited"
        finally:
            cleanup_authenticated_client(original_hash, original_db_path)
