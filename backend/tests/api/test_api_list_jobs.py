"""Tests for GET /jobs endpoint."""

import tempfile
import time

from app.auth.passwords import hash_password
from app.main import create_app
from fastapi.testclient import TestClient


def test_list_jobs_empty_returns_empty_array():
    """GET /jobs returns empty array when no jobs exist."""
    correct_password = "test_password"
    correct_hash = hash_password(correct_password)

    with tempfile.TemporaryDirectory() as tmpdir:
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
            import app.auth.config

            original_hash = app.auth.config.settings.auth_password_hash
            app.auth.config.settings.auth_password_hash = correct_hash

            try:
                test_client = TestClient(create_app())

                # Log in to get session cookie
                auth_response = test_client.post("/auth", json={"password": correct_password})
                assert auth_response.status_code == 200
                sid = auth_response.cookies.get("sid")
                assert sid is not None

                response = test_client.get("/jobs", cookies={"sid": sid})
                assert response.status_code == 200
                data = response.json()
                assert data == {"jobs": []}

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


def test_list_jobs_after_creation_returns_one():
    """GET /jobs returns one job after creating it."""
    correct_password = "test_password"
    correct_hash = hash_password(correct_password)

    with tempfile.TemporaryDirectory() as tmpdir:
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
            import app.auth.config

            original_hash = app.auth.config.settings.auth_password_hash
            app.auth.config.settings.auth_password_hash = correct_hash

            try:
                test_client = TestClient(create_app())

                # Log in to get session cookie
                auth_response = test_client.post("/auth", json={"password": correct_password})
                assert auth_response.status_code == 200
                sid = auth_response.cookies.get("sid")
                assert sid is not None

                # Create a job via preview
                conn = get_connection()
                from app.jobs.service import create_preview_job

                result = create_preview_job(
                    conn,
                    text="Jefe de Compras\nGerente de Ventas\nIngeniero de Software",
                    threshold=90,
                    titles_per_request=25,
                )
                conn.close()

                response = test_client.get("/jobs", cookies={"sid": sid})
                assert response.status_code == 200
                data = response.json()
                assert len(data["jobs"]) == 1
                assert data["jobs"][0]["id"] == result.job_id
                assert data["jobs"][0]["status"] == "preview"
                assert data["jobs"][0]["total_rows"] == 3
                assert data["jobs"][0]["cluster_count"] > 0
                assert "created_at" in data["jobs"][0]

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


def test_list_jobs_ordered_newest_first():
    """GET /jobs returns jobs ordered newest first."""
    correct_password = "test_password"
    correct_hash = hash_password(correct_password)

    with tempfile.TemporaryDirectory() as tmpdir:
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
            import app.auth.config

            original_hash = app.auth.config.settings.auth_password_hash
            app.auth.config.settings.auth_password_hash = correct_hash

            try:
                test_client = TestClient(create_app())

                # Log in to get session cookie
                auth_response = test_client.post("/auth", json={"password": correct_password})
                assert auth_response.status_code == 200
                sid = auth_response.cookies.get("sid")
                assert sid is not None

                # Create two jobs
                conn = get_connection()
                from app.jobs.service import create_preview_job

                result1 = create_preview_job(
                    conn,
                    text="Job 1\nJob 2",
                    threshold=90,
                    titles_per_request=25,
                )

                # Delay to ensure different timestamps (unixepoch has 1s precision)
                time.sleep(1.1)

                result2 = create_preview_job(
                    conn,
                    text="Job 3\nJob 4",
                    threshold=90,
                    titles_per_request=25,
                )
                conn.close()

                response = test_client.get("/jobs", cookies={"sid": sid})
                assert response.status_code == 200
                data = response.json()
                assert len(data["jobs"]) == 2
                # result2 should be first (newer)
                assert data["jobs"][0]["id"] == result2.job_id
                assert data["jobs"][1]["id"] == result1.job_id

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


def test_list_jobs_requires_auth():
    """GET /jobs returns 401 without authentication."""
    with tempfile.TemporaryDirectory() as tmpdir:
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

            test_client = TestClient(create_app())

            response = test_client.get("/jobs")
            assert response.status_code == 401
            data = response.json()
            assert "error" in data
            assert data["error"]["code"] == "unauthenticated"
        finally:
            app.settings.settings.database_path = original_db_path
