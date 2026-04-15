import tempfile

from app.auth.passwords import hash_password
from tests.anthropic.fake_client import FakeAnthropicBatchClient


def test_commit_dry_run_returns_202():
    """Test that commit with is_dry_run=True returns 202 and job transitions to completed."""
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
                # Create a new client that uses the temp database
                from fastapi.testclient import TestClient

                from app.main import create_app

                test_client = TestClient(create_app())
                test_client.app.state.anthropic_client = FakeAnthropicBatchClient()

                # Authenticate
                response = test_client.post("/auth", json={"password": correct_password})
                assert response.status_code == 200

                # Get session cookie
                sid = response.cookies.get("sid")
                assert sid is not None

                # Create a preview job
                csv_data = b"Jefe de Compras\nJefe de Ventas\nIngeniero de Software"
                response = test_client.post(
                    "/jobs/preview",
                    files={"file": ("test.csv", csv_data, "text/csv")},
                    cookies={"sid": sid},
                )
                assert response.status_code == 200
                job_id = response.json()["job_id"]

                # Commit with is_dry_run=True
                response = test_client.post(
                    f"/jobs/{job_id}/commit",
                    json={"is_dry_run": True},
                    cookies={"sid": sid},
                )
                assert response.status_code == 202

                # Verify job is completed (not submitted/polling)
                response = test_client.get(f"/jobs/{job_id}", cookies={"sid": sid})
                assert response.status_code == 200
                assert response.json()["status"] == "completed"
                response = test_client.get(f"/jobs/{job_id}", cookies={"sid": sid})
                assert response.status_code == 200
                assert response.json()["status"] == "completed"

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


def test_dry_run_job_shows_is_dry_run_in_detail():
    """Test that dry_run jobs have is_dry_run=True in job detail response."""
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
                # Create a new client that uses the temp database
                from fastapi.testclient import TestClient

                from app.main import create_app

                test_client = TestClient(create_app())
                test_client.app.state.anthropic_client = FakeAnthropicBatchClient()

                # Authenticate
                response = test_client.post("/auth", json={"password": correct_password})
                assert response.status_code == 200

                # Get session cookie
                sid = response.cookies.get("sid")
                assert sid is not None

                # Create a preview job
                csv_data = b"Jefe de Compras\nJefe de Ventas\nIngeniero de Software"
                response = test_client.post(
                    "/jobs/preview",
                    files={"file": ("test.csv", csv_data, "text/csv")},
                    cookies={"sid": sid},
                )
                assert response.status_code == 200
                job_id = response.json()["job_id"]

                # Commit with is_dry_run=True
                response = test_client.post(
                    f"/jobs/{job_id}/commit",
                    json={"is_dry_run": True},
                    cookies={"sid": sid},
                )
                assert response.status_code == 202

                # Verify job shows is_dry_run=True
                response = test_client.get(f"/jobs/{job_id}", cookies={"sid": sid})
                assert response.status_code == 200
                assert response.json()["is_dry_run"] is True

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


def test_dry_run_job_shows_zero_cost():
    """Test that dry_run jobs have zero actual_cost_usd."""
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
                # Create a new client that uses the temp database
                from fastapi.testclient import TestClient

                from app.main import create_app

                test_client = TestClient(create_app())
                test_client.app.state.anthropic_client = FakeAnthropicBatchClient()

                # Authenticate
                response = test_client.post("/auth", json={"password": correct_password})
                assert response.status_code == 200

                # Get session cookie
                sid = response.cookies.get("sid")
                assert sid is not None

                # Create a preview job
                csv_data = b"Jefe de Compras\nJefe de Ventas\nIngeniero de Software"
                response = test_client.post(
                    "/jobs/preview",
                    files={"file": ("test.csv", csv_data, "text/csv")},
                    cookies={"sid": sid},
                )
                assert response.status_code == 200
                job_id = response.json()["job_id"]

                # Commit with is_dry_run=True
                response = test_client.post(
                    f"/jobs/{job_id}/commit",
                    json={"is_dry_run": True},
                    cookies={"sid": sid},
                )
                assert response.status_code == 202

                # Verify job has zero actual cost
                response = test_client.get(f"/jobs/{job_id}", cookies={"sid": sid})
                assert response.status_code == 200
                assert response.json()["actual_cost_usd"] == 0.0

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


def test_dry_run_completes_without_worker():
    """Test that dry_run jobs complete immediately without requiring worker polling."""
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
                # Create a new client that uses the temp database
                from fastapi.testclient import TestClient

                from app.main import create_app

                test_client = TestClient(create_app())
                test_client.app.state.anthropic_client = FakeAnthropicBatchClient()

                # Authenticate
                response = test_client.post("/auth", json={"password": correct_password})
                assert response.status_code == 200

                # Get session cookie
                sid = response.cookies.get("sid")
                assert sid is not None

                # Create a preview job
                csv_data = b"Jefe de Compras\nJefe de Ventas\nIngeniero de Software"
                response = test_client.post(
                    "/jobs/preview",
                    files={"file": ("test.csv", csv_data, "text/csv")},
                    cookies={"sid": sid},
                )
                assert response.status_code == 200
                job_id = response.json()["job_id"]

                # Job should be in preview state
                response = test_client.get(f"/jobs/{job_id}", cookies={"sid": sid})
                assert response.status_code == 200
                assert response.json()["status"] == "preview"

                # Commit with is_dry_run=True
                response = test_client.post(
                    f"/jobs/{job_id}/commit",
                    json={"is_dry_run": True},
                    cookies={"sid": sid},
                )
                assert response.status_code == 202

                # Job should be completed immediately (not submitted/polling)
                response = test_client.get(f"/jobs/{job_id}", cookies={"sid": sid})
                assert response.status_code == 200
                assert response.json()["status"] == "completed"

                # No batches should exist (dry run doesn't submit to Anthropic)
                batches = response.json()["batches"]
                assert len(batches) == 0

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path
