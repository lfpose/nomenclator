"""Tests for GET /jobs/:id endpoint."""

import tempfile

from app.auth.passwords import hash_password
from app.dao.clusters import update_cluster_answers
from app.main import create_app
from fastapi.testclient import TestClient


def test_get_job_returns_progress_counts():
    """GET /jobs/:id returns progress counts for clusters."""
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
                    text="Jefe de Compras\nGerente de Ventas\nIngeniero de Software\nDirector de Marketing",
                    threshold=90,
                    titles_per_request=25,
                )

                # Mark some clusters as resolved and one as errored
                from app.dao.clusters import list_clusters

                clusters = list_clusters(conn, result.job_id)
                if len(clusters) >= 2:
                    update_cluster_answers(
                        conn,
                        clusters[0].id,
                        male_es="Jefe de Compras",
                        female_es="Jefa de Compras",
                        category="Management",
                    )
                    update_cluster_answers(
                        conn,
                        clusters[1].id,
                        male_es="Gerente de Ventas",
                        female_es="Gerenta de Ventas",
                        category="Management",
                    )
                if len(clusters) >= 3:
                    from app.dao.clusters import mark_cluster_error
                    mark_cluster_error(conn, clusters[2].id, "test_error")

                conn.close()

                response = test_client.get(f"/jobs/{result.job_id}", cookies={"sid": sid})
                assert response.status_code == 200
                data = response.json()

                assert "progress" in data
                assert data["progress"]["clusters_total"] >= len(clusters)
                assert data["progress"]["clusters_resolved"] >= 2
                assert data["progress"]["clusters_error"] >= 1
                assert "clusters_pending" in data["progress"]
            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


def test_get_job_returns_batches_array():
    """GET /jobs/:id returns batches array with batch details."""
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

                response = test_client.get(f"/jobs/{result.job_id}", cookies={"sid": sid})
                assert response.status_code == 200
                data = response.json()

                assert "batches" in data
                # Preview jobs have no batches yet (empty array is expected)
                assert isinstance(data["batches"], list)

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


def test_get_job_retry_round_reflects_max():
    """GET /jobs/:id returns the maximum retry_round from batches."""
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

                # Insert some batches with different retry_round values
                import uuid
                from app.dao.batches import insert_batch
                from app.dao.batch_requests import insert_request

                batch1_id = str(uuid.uuid4())
                batch2_id = str(uuid.uuid4())
                insert_batch(
                    conn,
                    id=batch1_id,
                    job_id=result.job_id,
                    retry_round=0,
                    parent_batch_id=None,
                    status="in_progress",
                    request_count=2,
                )
                insert_batch(
                    conn,
                    id=batch2_id,
                    job_id=result.job_id,
                    retry_round=2,
                    parent_batch_id=None,
                    status="in_progress",
                    request_count=1,
                )
                insert_request(
                    conn,
                    id=str(uuid.uuid4()),
                    batch_id=batch1_id,
                    cluster_ids=[1, 2],
                )
                insert_request(
                    conn,
                    id=str(uuid.uuid4()),
                    batch_id=batch2_id,
                    cluster_ids=[3],
                )

                conn.close()

                response = test_client.get(f"/jobs/{result.job_id}", cookies={"sid": sid})
                assert response.status_code == 200
                data = response.json()

                assert "retry_round" in data
                assert data["retry_round"] == 2  # Max of 0 and 2

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


def test_get_job_missing_404():
    """GET /jobs/:id returns 404 for non-existent job."""
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

                # Try to get a non-existent job
                response = test_client.get("/jobs/nonexistent-job-id", cookies={"sid": sid})
                assert response.status_code == 404
                data = response.json()
                assert "error" in data
                assert data["error"]["code"] == "job_not_found"

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path
