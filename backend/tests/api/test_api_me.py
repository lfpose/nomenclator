import tempfile

from app.auth.passwords import hash_password


def test_me_401_without_cookie():
    """Test that /me returns 401 without session cookie."""
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

                # Test /me without cookie should return 401
                response = test_client.get("/me")
                assert response.status_code == 401

                # Check error envelope
                data = response.json()
                assert "error" in data
                assert data["error"]["code"] == "unauthenticated"
                assert data["error"]["message"] == "Session required."

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


def test_me_200_with_valid_cookie():
    """Test that /me returns 200 with valid session cookie."""
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

                # First, log in to get a session cookie
                auth_response = test_client.post(
                    "/auth", json={"password": correct_password}
                )
                assert auth_response.status_code == 200

                # Extract the cookie value
                sid = auth_response.cookies.get("sid")
                assert sid is not None

                # Now test /me with the session cookie
                response = test_client.get("/me", cookies={"sid": sid})
                assert response.status_code == 200

                # Check response
                data = response.json()
                assert data == {"authenticated": True}

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


def test_logout_destroys_session():
    """Test that /auth/logout destroys the session."""
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

                # First, log in to get a session cookie
                auth_response = test_client.post(
                    "/auth", json={"password": correct_password}
                )
                assert auth_response.status_code == 200

                # Extract the cookie value
                sid = auth_response.cookies.get("sid")
                assert sid is not None

                # Now logout
                logout_response = test_client.post("/auth/logout", cookies={"sid": sid})
                assert logout_response.status_code == 200

                # Check response
                data = logout_response.json()
                assert data == {"ok": True}

                # Check that cookie is deleted
                set_cookie_header = logout_response.headers.get("set-cookie")
                assert set_cookie_header is not None
                # Cookie deletion uses Max-Age=0
                assert "Max-Age=0" in set_cookie_header

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


def test_me_401_after_logout():
    """Test that /me returns 401 after logout."""
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

                # First, log in to get a session cookie
                auth_response = test_client.post(
                    "/auth", json={"password": correct_password}
                )
                assert auth_response.status_code == 200

                # Extract the cookie value
                sid = auth_response.cookies.get("sid")
                assert sid is not None

                # Verify /me works before logout
                me_response = test_client.get("/me", cookies={"sid": sid})
                assert me_response.status_code == 200

                # Now logout
                logout_response = test_client.post("/auth/logout", cookies={"sid": sid})
                assert logout_response.status_code == 200

                # Now test /me with the same cookie - should return 401
                response = test_client.get("/me", cookies={"sid": sid})
                assert response.status_code == 401

                # Check error envelope
                data = response.json()
                assert "error" in data
                assert data["error"]["code"] == "unauthenticated"
                assert data["error"]["message"] == "Session required."

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path
