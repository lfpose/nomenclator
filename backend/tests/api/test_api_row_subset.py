import tempfile

from app.auth.passwords import hash_password


def test_preview_first_n_returns_subset_count():
    """Test that preview with row_subset_mode='first_n' processes only n rows."""
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

                # Create a CSV with 10 rows
                csv_data = "Jefe de Compras\nJefe de Ventas\nIngeniero de Software\nDirector de Marketing\nGerente de RRHH\nAnalista de Datos\nDiseñador UI/UX\nProduct Manager\nQA Engineer\nDevOps Engineer".encode("utf-8")

                # Preview with first_n=5
                response = test_client.post(
                    "/jobs/preview",
                    data={
                        "threshold": 90,
                        "titles_per_request": 25,
                        "row_subset_mode": "first_n",
                        "row_subset_n": 5,
                    },
                    files={"file": ("test.csv", csv_data, "text/csv")},
                    cookies={"sid": sid},
                )
                assert response.status_code == 200

                # Verify only 5 rows were processed
                data = response.json()
                assert data["total_rows"] == 5

                # Verify job has row_subset_mode and row_subset_n
                job_id = data["job_id"]
                response = test_client.get(f"/jobs/{job_id}", cookies={"sid": sid})
                assert response.status_code == 200
                job_data = response.json()
                assert job_data["row_subset_mode"] == "first_n"
                assert job_data["row_subset_n"] == 5

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


def test_preview_random_n_returns_subset_count():
    """Test that preview with row_subset_mode='random_n' processes exactly n rows."""
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

                # Create a CSV with 20 rows
                csv_lines = "\n".join(f"Job Title {i}" for i in range(20)).encode("utf-8")

                # Preview with random_n=10
                response = test_client.post(
                    "/jobs/preview",
                    data={
                        "threshold": 90,
                        "titles_per_request": 25,
                        "row_subset_mode": "random_n",
                        "row_subset_n": 10,
                    },
                    files={"file": ("test.csv", csv_lines, "text/csv")},
                    cookies={"sid": sid},
                )
                assert response.status_code == 200

                # Verify exactly 10 rows were processed
                data = response.json()
                assert data["total_rows"] == 10

                # Verify job has row_subset_mode and row_subset_n
                job_id = data["job_id"]
                response = test_client.get(f"/jobs/{job_id}", cookies={"sid": sid})
                assert response.status_code == 200
                job_data = response.json()
                assert job_data["row_subset_mode"] == "random_n"
                assert job_data["row_subset_n"] == 10

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


def test_preview_bad_row_subset_mode_400():
    """Test that preview with invalid row_subset_mode returns 400."""
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

                # Create a CSV
                csv_data = b"Jefe de Compras\nJefe de Ventas\nIngeniero de Software"

                # Preview with invalid row_subset_mode
                response = test_client.post(
                    "/jobs/preview",
                    data={
                        "threshold": 90,
                        "titles_per_request": 25,
                        "row_subset_mode": "invalid_mode",
                        "row_subset_n": 5,
                    },
                    files={"file": ("test.csv", csv_data, "text/csv")},
                    cookies={"sid": sid},
                )
                assert response.status_code == 400

                # Check error envelope
                data = response.json()
                assert "error" in data
                assert data["error"]["code"] == "bad_row_subset_mode"

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


def test_preview_missing_n_when_not_all_400():
    """Test that preview with mode='first_n' but missing n returns 400."""
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

                # Create a CSV
                csv_data = b"Jefe de Compras\nJefe de Ventas\nIngeniero de Software"

                # Preview with first_n but missing n
                response = test_client.post(
                    "/jobs/preview",
                    data={
                        "threshold": 90,
                        "titles_per_request": 25,
                        "row_subset_mode": "first_n",
                    },
                    files={"file": ("test.csv", csv_data, "text/csv")},
                    cookies={"sid": sid},
                )
                assert response.status_code == 400

                # Check error envelope
                data = response.json()
                assert "error" in data
                assert data["error"]["code"] == "bad_row_subset_n"

                # Test with n=0 (should also fail)
                response = test_client.post(
                    "/jobs/preview",
                    data={
                        "threshold": 90,
                        "titles_per_request": 25,
                        "row_subset_mode": "first_n",
                        "row_subset_n": 0,
                    },
                    files={"file": ("test.csv", csv_data, "text/csv")},
                    cookies={"sid": sid},
                )
                assert response.status_code == 400

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path
