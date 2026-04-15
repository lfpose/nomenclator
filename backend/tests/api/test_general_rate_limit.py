import tempfile

from app.auth.passwords import hash_password


def test_general_rate_limit_blocks_after_60():
    """Test that general rate limit blocks after 60 requests."""
    # Monkeypatch the password hash to a known hash
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

                # Authenticate
                response = test_client.post("/auth", json={"password": correct_password})
                assert response.status_code == 200

                # Get session cookie
                sid = response.cookies.get("sid")
                assert sid is not None

                # Make 60 requests to an authenticated endpoint - all should succeed
                for i in range(60):
                    response = test_client.get("/jobs", cookies={"sid": sid})
                    assert response.status_code == 200

                # 61st request should be rate limited
                response = test_client.get("/jobs", cookies={"sid": sid})
                assert response.status_code == 429

                # Check error envelope
                data = response.json()
                assert "error" in data
                assert data["error"]["code"] == "rate_limited"
                assert data["error"]["message"] == "Too many requests."

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


def test_general_rate_limit_separate_per_session():
    """Test that general rate limiting is separate per session."""
    # Monkeypatch the password hash to a known hash
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

                # Authenticate first session
                response = test_client.post("/auth", json={"password": correct_password})
                assert response.status_code == 200
                sid1 = response.cookies.get("sid")
                assert sid1 is not None

                # Create a second session by clearing cookies and re-authenticating
                test_client.cookies.clear()
                response = test_client.post("/auth", json={"password": correct_password})
                assert response.status_code == 200
                sid2 = response.cookies.get("sid")
                assert sid2 is not None
                assert sid2 != sid1

                # Exhaust rate limit on session 1 (60 requests)
                for i in range(60):
                    response = test_client.get("/jobs", cookies={"sid": sid1})
                    assert response.status_code == 200

                # Session 1 should be rate limited
                response = test_client.get("/jobs", cookies={"sid": sid1})
                assert response.status_code == 429

                # Session 2 should still work (independent rate limit)
                response = test_client.get("/jobs", cookies={"sid": sid2})
                assert response.status_code == 200

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path
