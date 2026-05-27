import tempfile

import pytest

from app.auth.passwords import hash_password


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

            test_client = TestClient(create_app())

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


def cleanup_authenticated_client(original_hash: str, original_db_path: str, test_ip: str | None = None):
    """Helper to clean up after get_authenticated_client."""
    import app.auth.config
    import app.settings

    app.auth.config.settings.auth_password_hash = original_hash
    app.settings.settings.database_path = original_db_path


def test_preview_with_csv_file_returns_payload():
    """Test that /jobs/preview returns payload with CSV file input."""
    test_ip = "127.0.0.1"
    with tempfile.TemporaryDirectory() as tmpdir:
        test_client, sid, original_hash, original_db_path = get_authenticated_client(tmpdir, test_ip)

        try:
            # Create a simple CSV file with job titles
            csv_content = b"""Jefe de Compras
Jefe de ventas
Ingeniero de Software
Director de Marketing
Gerente de Recursos Humanos"""

            # Upload the CSV file
            response = test_client.post(
                "/jobs/preview",
                data={
                    "threshold": 90,
                    "titles_per_request": 25,
                },
                files={"file": ("test.csv", csv_content, "text/csv")},
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )

            assert response.status_code == 200

            # Check the response payload
            data = response.json()
            assert "job_id" in data
            assert "total_rows" in data
            assert "exact_unique_rows" in data
            assert "cluster_count" in data
            assert "largest_cluster_size" in data
            assert "est_cost_usd" in data
            assert "top_clusters" in data
            assert "warnings" in data

            # Verify job_id is a string
            assert isinstance(data["job_id"], str)

            # Verify counts
            assert data["total_rows"] == 5
            assert data["exact_unique_rows"] == 5
            assert data["cluster_count"] >= 1

            # Verify est_cost_usd is rounded to 4 decimal places
            assert len(str(data["est_cost_usd"]).split(".")[-1]) <= 4

        finally:
            cleanup_authenticated_client(original_hash, original_db_path)


def test_preview_with_pasted_text_returns_payload():
    """Test that /jobs/preview returns payload with pasted text input."""
    test_ip = "127.0.0.2"
    with tempfile.TemporaryDirectory() as tmpdir:
        test_client, sid, original_hash, original_db_path = get_authenticated_client(tmpdir, test_ip)

        try:
            # Create text content with job titles
            text_content = "Jefe de Compras\nJefe de ventas\nIngeniero de Software\nDirector de Marketing\nGerente de Recursos Humanos"

            # Submit the text content
            response = test_client.post(
                "/jobs/preview",
                data={
                    "threshold": 90,
                    "titles_per_request": 25,
                    "text": text_content,
                },
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )

            assert response.status_code == 200

            # Check the response payload
            data = response.json()
            assert "job_id" in data
            assert "total_rows" in data
            assert data["total_rows"] == 5
            assert data["exact_unique_rows"] == 5
            assert "cluster_count" in data

        finally:
            cleanup_authenticated_client(original_hash, original_db_path)


def test_preview_bad_threshold_400():
    """Test that /jobs/preview returns 400 for bad threshold."""
    test_ip = "127.0.0.3"
    with tempfile.TemporaryDirectory() as tmpdir:
        test_client, sid, original_hash, original_db_path = get_authenticated_client(tmpdir, test_ip)

        try:
            # Test threshold below 50
            response = test_client.post(
                "/jobs/preview",
                data={
                    "threshold": 40,  # Invalid: < 50
                    "titles_per_request": 25,
                    "text": "Jefe de Compras\n",
                },
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )

            assert response.status_code == 400

            # Check error envelope
            data = response.json()
            assert "error" in data
            assert data["error"]["code"] == "bad_threshold"
            assert "50–100" in data["error"]["message"]

            # Test threshold above 100
            response = test_client.post(
                "/jobs/preview",
                data={
                    "threshold": 110,  # Invalid: > 100
                    "titles_per_request": 25,
                    "text": "Jefe de Compras\n",
                },
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )

            assert response.status_code == 400
            assert data["error"]["code"] == "bad_threshold"

        finally:
            cleanup_authenticated_client(original_hash, original_db_path)


def test_preview_bad_tpr_400():
    """Test that /jobs/preview returns 400 for bad titles_per_request."""
    test_ip = "127.0.0.4"
    with tempfile.TemporaryDirectory() as tmpdir:
        test_client, sid, original_hash, original_db_path = get_authenticated_client(tmpdir, test_ip)

        try:
            # Test TPR below 1
            response = test_client.post(
                "/jobs/preview",
                data={
                    "threshold": 90,
                    "titles_per_request": 0,  # Invalid: < 1
                    "text": "Jefe de Compras\n",
                },
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )

            assert response.status_code == 400

            # Check error envelope
            data = response.json()
            assert "error" in data
            assert data["error"]["code"] == "bad_titles_per_request"
            assert "1–50" in data["error"]["message"]

            # Test TPR above 50
            response = test_client.post(
                "/jobs/preview",
                data={
                    "threshold": 90,
                    "titles_per_request": 60,  # Invalid: > 50
                    "text": "Jefe de Compras\n",
                },
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )

            assert response.status_code == 400
            assert data["error"]["code"] == "bad_titles_per_request"

        finally:
            cleanup_authenticated_client(original_hash, original_db_path)


def test_preview_empty_csv_400():
    """Test that /jobs/preview returns 400 for empty CSV."""
    test_ip = "127.0.0.5"
    with tempfile.TemporaryDirectory() as tmpdir:
        test_client, sid, original_hash, original_db_path = get_authenticated_client(tmpdir, test_ip)

        try:
            # Test empty CSV file
            csv_content = b""

            response = test_client.post(
                "/jobs/preview",
                data={
                    "threshold": 90,
                    "titles_per_request": 25,
                },
                files={"file": ("test.csv", csv_content, "text/csv")},
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )

            assert response.status_code == 400

            # Check error envelope
            data = response.json()
            assert "error" in data
            assert data["error"]["code"] == "input_empty"

            # Test empty text
            response = test_client.post(
                "/jobs/preview",
                data={
                    "threshold": 90,
                    "titles_per_request": 25,
                    "text": "",  # Empty text
                },
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )

            assert response.status_code == 400
            assert data["error"]["code"] == "input_empty"

        finally:
            cleanup_authenticated_client(original_hash, original_db_path)


def test_preview_requires_auth():
    """Test that /jobs/preview returns 401 without authentication."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Monkeypatch settings to use temp database
        import app.settings

        original_db_path = app.settings.settings.database_path
        app.settings.settings.database_path = f"{tmpdir}/test.db"

        try:
            # Initialize database
            from app.db import get_connection

            conn = get_connection()
            conn.close()

            # Create a new client without authentication
            from fastapi.testclient import TestClient

            from app.main import create_app

            test_client = TestClient(create_app())

            # Try to access /jobs/preview without auth
            response = test_client.post(
                "/jobs/preview",
                data={
                    "threshold": 90,
                    "titles_per_request": 25,
                    "text": "Jefe de Compras\n",
                },
            )

            assert response.status_code == 401

            # Check error envelope
            data = response.json()
            assert "error" in data
            assert data["error"]["code"] == "unauthenticated"

        finally:
            # Restore db path
            app.settings.settings.database_path = original_db_path


def test_preview_returns_job_id_in_preview_state():
    """Test that /jobs/preview creates job in preview state."""
    test_ip = "127.0.0.6"
    with tempfile.TemporaryDirectory() as tmpdir:
        test_client, sid, original_hash, original_db_path = get_authenticated_client(tmpdir, test_ip)

        try:
            # Create a simple CSV file
            csv_content = b"Jefe de Compras\nJefe de ventas\n"

            # Upload the CSV file
            response = test_client.post(
                "/jobs/preview",
                data={
                    "threshold": 90,
                    "titles_per_request": 25,
                },
                files={"file": ("test.csv", csv_content, "text/csv")},
                cookies={"sid": sid},
                headers={"X-Forwarded-For": test_ip},
            )

            assert response.status_code == 200

            # Get the job_id from the response
            data = response.json()
            job_id = data["job_id"]

            # Verify the job is in preview state by checking the job directly from the database
            from app.dao.jobs import get_job
            from app.db import get_connection

            conn = get_connection()
            job = get_job(conn, job_id)
            conn.close()

            assert job is not None
            assert job.status == "preview"

        finally:
            cleanup_authenticated_client(original_hash, original_db_path)
