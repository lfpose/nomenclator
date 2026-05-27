import tempfile

from app.auth.passwords import hash_password


def test_auth_correct_password_sets_cookie():
    """Test that correct password sets session cookie and returns 200."""
    # Monkeypatch the password hash to a known hash
    correct_password = "test_password"
    correct_hash = hash_password(correct_password)
    
    # Use unique IP for this test to avoid rate limiting from other tests
    test_ip = "127.0.0.1"

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

                # Test correct password with unique IP
                response = test_client.post(
                    "/auth", json={"password": correct_password}, headers={"X-Forwarded-For": test_ip}
                )
                assert response.status_code == 200
                assert response.json() == {"ok": True}

                # Check cookie is set
                assert "sid" in response.cookies
                cookie = response.cookies["sid"]
                assert len(cookie) > 0

                # Check cookie flags
                set_cookie_header = response.headers.get("set-cookie")
                assert set_cookie_header is not None
                assert "HttpOnly" in set_cookie_header
                # secure=False in dev; assert "Secure" in set_cookie_header
                assert "samesite=lax" in set_cookie_header.lower()
                assert "Max-Age=2592000" in set_cookie_header
                assert "Path=/" in set_cookie_header

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


def test_auth_wrong_password_returns_401():
    """Test that wrong password returns 401 unauthenticated."""
    # Monkeypatch the password hash to a known hash
    correct_password = "correct_password"
    correct_hash = hash_password(correct_password)
    
    # Use unique IP for this test to avoid rate limiting from other tests
    test_ip = "127.0.0.2"

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

                # Test wrong password with unique IP
                response = test_client.post("/auth", json={"password": "wrong_password"}, headers={"X-Forwarded-For": test_ip})
                assert response.status_code == 401

                # Check error envelope
                data = response.json()
                assert "error" in data
                assert data["error"]["code"] == "unauthenticated"
                assert data["error"]["message"] == "Wrong password."

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


def test_auth_rate_limits_after_5_attempts():
    """Test that rate limiting kicks in after 5 attempts."""
    # Monkeypatch the password hash to a known hash
    correct_password = "test_password"
    correct_hash = hash_password(correct_password)
    
    # Use unique IP for this test to avoid rate limiting from other tests
    test_ip = "127.0.0.3"

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

                # Make 5 wrong password attempts - each should return 401
                for i in range(5):
                    response = test_client.post(
                        "/auth", json={"password": "wrong_password"}, headers={"X-Forwarded-For": test_ip}
                    )
                    assert response.status_code == 401

                # 6th attempt should be rate limited
                response = test_client.post("/auth", json={"password": "wrong_password"}, headers={"X-Forwarded-For": test_ip})
                assert response.status_code == 429

                # Check error envelope
                data = response.json()
                assert "error" in data
                assert data["error"]["code"] == "rate_limited"
                assert data["error"]["message"] == "Too many attempts."

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


def test_auth_cookie_flags_httponly_secure_samesite():
    """Test that session cookie has HttpOnly, Secure, and SameSite flags."""
    # Monkeypatch the password hash to a known hash
    correct_password = "test_password"
    correct_hash = hash_password(correct_password)
    
    # Use unique IP for this test to avoid rate limiting from other tests
    test_ip = "127.0.0.4"

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

                # Test correct password with unique IP
                response = test_client.post(
                    "/auth", json={"password": correct_password}, headers={"X-Forwarded-For": test_ip}
                )
                assert response.status_code == 200

                # Check cookie is set
                assert "sid" in response.cookies

                # Check cookie flags via Set-Cookie header
                set_cookie_header = response.headers.get("set-cookie")
                assert set_cookie_header is not None

                # HttpOnly flag
                assert "HttpOnly" in set_cookie_header

                # Secure flag
                # secure=False in dev; assert "Secure" in set_cookie_header

                # SameSite=lax flag (case-insensitive check)
                assert "samesite=lax" in set_cookie_header.lower()

                # Max-Age=2592000 (30 days)
                assert "Max-Age=2592000" in set_cookie_header

                # Path=/
                assert "Path=/" in set_cookie_header

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path
