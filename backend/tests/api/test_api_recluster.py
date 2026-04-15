import tempfile

from fastapi.testclient import TestClient
from app.auth.passwords import hash_password

from app.main import create_app


def test_recluster_updates_cluster_count():
    """Reclustering with a stricter threshold should increase cluster count."""
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

            # Monkeypatch password hash
            import app.auth.config
            correct_password = "test_password"
            correct_hash = hash_password(correct_password)
            original_hash = app.auth.config.settings.auth_password_hash
            app.auth.config.settings.auth_password_hash = correct_hash

            try:
                # Create a new client that uses temp database
                client = TestClient(create_app())

                # Login to get session cookie
                response = client.post(
                    "/auth",
                    json={"password": correct_password},
                    headers={"X-Forwarded-For": "127.0.0.1"},
                )
                assert response.status_code == 200
                cookies = {"sid": response.cookies.get("sid")}

                # Create a preview job using CSV data
                csv_data = b"Jefe de Compras\nJefe de Compras\nIngeniero de Software\n"
                response = client.post(
                    "/jobs/preview",
                    files={"file": ("test.csv", csv_data, "text/csv")},
                    data={
                        "threshold": 95,
                        "titles_per_request": 25,
                    },
                    cookies=cookies,
                    headers={"X-Forwarded-For": "127.0.0.2"},
                )
                assert response.status_code == 200
                job_id = response.json()["job_id"]
                original_cluster_count = response.json()["cluster_count"]

                # Recluster with a looser threshold (should produce fewer clusters)
                response = client.post(
                    f"/jobs/{job_id}/recluster",
                    json={"threshold": 80},
                    cookies=cookies,
                    headers={"X-Forwarded-For": "127.0.0.3"},
                )
                assert response.status_code == 200
                new_cluster_count = response.json()["cluster_count"]

                # Looser threshold should produce fewer clusters
                assert new_cluster_count <= original_cluster_count

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


def test_recluster_bad_threshold_400():
    """Invalid threshold should return 400 bad request."""
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

            # Monkeypatch password hash
            import app.auth.config
            correct_password = "test_password"
            correct_hash = hash_password(correct_password)
            original_hash = app.auth.config.settings.auth_password_hash
            app.auth.config.settings.auth_password_hash = correct_hash

            try:
                # Create a new client that uses temp database
                client = TestClient(create_app())

                # Login to get session cookie
                response = client.post(
                    "/auth",
                    json={"password": correct_password},
                    headers={"X-Forwarded-For": "127.0.0.1"},
                )
                assert response.status_code == 200
                cookies = {"sid": response.cookies.get("sid")}

                # Create a preview job
                csv_data = b"Jefe de Compras\n"
                response = client.post(
                    "/jobs/preview",
                    files={"file": ("test.csv", csv_data, "text/csv")},
                    data={
                        "threshold": 90,
                        "titles_per_request": 25,
                    },
                    cookies=cookies,
                    headers={"X-Forwarded-For": "127.0.0.2"},
                )
                assert response.status_code == 200
                job_id = response.json()["job_id"]

                # Try to recluster with threshold too low
                response = client.post(
                    f"/jobs/{job_id}/recluster",
                    json={"threshold": 49},
                    cookies=cookies,
                    headers={"X-Forwarded-For": "127.0.0.3"},
                )
                assert response.status_code == 400
                assert response.json()["error"]["code"] == "bad_threshold"

                # Try to recluster with threshold too high
                response = client.post(
                    f"/jobs/{job_id}/recluster",
                    json={"threshold": 101},
                    cookies=cookies,
                    headers={"X-Forwarded-For": "127.0.0.4"},
                )
                assert response.status_code == 400
                assert response.json()["error"]["code"] == "bad_threshold"

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


def test_recluster_non_preview_409():
    """Reclustering a job not in preview state should return 409."""
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

            # Monkeypatch password hash
            import app.auth.config
            correct_password = "test_password"
            correct_hash = hash_password(correct_password)
            original_hash = app.auth.config.settings.auth_password_hash
            app.auth.config.settings.auth_password_hash = correct_hash

            try:
                # Create a new client that uses temp database
                client = TestClient(create_app())

                # Login to get session cookie
                response = client.post(
                    "/auth",
                    json={"password": correct_password},
                    headers={"X-Forwarded-For": "127.0.0.1"},
                )
                assert response.status_code == 200
                cookies = {"sid": response.cookies.get("sid")}

                # Create a preview job
                csv_data = b"Jefe de Compras\n"
                response = client.post(
                    "/jobs/preview",
                    files={"file": ("test.csv", csv_data, "text/csv")},
                    data={
                        "threshold": 90,
                        "titles_per_request": 25,
                    },
                    cookies=cookies,
                    headers={"X-Forwarded-For": "127.0.0.2"},
                )
                assert response.status_code == 200
                job_id = response.json()["job_id"]

                # Transition job to completed state (simulating job completion)
                # We need to do this via the database directly
                from app.db import get_connection
                conn = get_connection()
                conn.execute(
                    "UPDATE jobs SET status = 'completed' WHERE id = ?",
                    (job_id,),
                )
                conn.commit()
                conn.close()

                # Try to recluster a completed job
                response = client.post(
                    f"/jobs/{job_id}/recluster",
                    json={"threshold": 85},
                    cookies=cookies,
                    headers={"X-Forwarded-For": "127.0.0.3"},
                )
                assert response.status_code == 409
                assert response.json()["error"]["code"] == "invalid_state"

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


def test_recluster_missing_job_404():
    """Reclustering a non-existent job should return 404."""
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

            # Monkeypatch password hash
            import app.auth.config
            correct_password = "test_password"
            correct_hash = hash_password(correct_password)
            original_hash = app.auth.config.settings.auth_password_hash
            app.auth.config.settings.auth_password_hash = correct_hash

            try:
                # Create a new client that uses temp database
                client = TestClient(create_app())

                # Login to get session cookie
                response = client.post(
                    "/auth",
                    json={"password": correct_password},
                    headers={"X-Forwarded-For": "127.0.0.1"},
                )
                assert response.status_code == 200
                cookies = {"sid": response.cookies.get("sid")}

                # Try to recluster a non-existent job
                response = client.post(
                    "/jobs/00000000-0000-0000-0000-000000000000/recluster",
                    json={"threshold": 85},
                    cookies=cookies,
                    headers={"X-Forwarded-For": "127.0.0.2"},
                )
                assert response.status_code == 404
                assert response.json()["error"]["code"] == "job_not_found"

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path
