import tempfile

from app.auth.passwords import hash_password


def test_review_prompt_returns_structured_review():
    """Test that review-prompt returns structured review with all fields."""
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

                # Mock the anthropic client to return a predefined review
                from unittest.mock import patch

                from app.anthropic.review import PromptReview

                mock_review = PromptReview(
                    safe=True,
                    quality_score="good",
                    issues=[],
                    suggestions=["Consider adding more few-shot examples"],
                    summary="Prompt is clear and well-structured.",
                )

                with patch(
                    "app.anthropic.review.review_prompt", return_value=mock_review
                ):
                    response = test_client.post(
                        "/jobs/review-prompt",
                        json={
                            "prompt": "Normalize job titles to Spanish",
                            "few_shots": "[]",
                        },
                        cookies={"sid": sid},
                    )
                    assert response.status_code == 200

                    # Check response structure
                    data = response.json()
                    assert data["safe"] is True
                    assert data["quality_score"] == "good"
                    assert data["issues"] == []
                    assert len(data["suggestions"]) == 1
                    assert data["summary"] == "Prompt is clear and well-structured."

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


def test_review_prompt_requires_auth():
    """Test that review-prompt requires authentication."""
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

            # Create a new client that uses the temp database
            from fastapi.testclient import TestClient

            from app.main import create_app

            test_client = TestClient(create_app())

            # Test without authentication
            response = test_client.post(
                "/jobs/review-prompt",
                json={
                    "prompt": "Normalize job titles to Spanish",
                    "few_shots": "[]",
                },
            )
            assert response.status_code == 401

            # Check error envelope
            data = response.json()
            assert "error" in data
            assert data["error"]["code"] == "unauthenticated"

        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


def test_review_prompt_rate_limited():
    """Test that review-prompt is rate limited after 10 requests."""
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

                # Mock the anthropic client
                from unittest.mock import patch

                from app.anthropic.review import PromptReview

                mock_review = PromptReview(
                    safe=True,
                    quality_score="good",
                    issues=[],
                    suggestions=[],
                    summary="OK",
                )

                with patch(
                    "app.anthropic.review.review_prompt", return_value=mock_review
                ):
                    # Make 10 review requests - all should succeed
                    for i in range(10):
                        response = test_client.post(
                            "/jobs/review-prompt",
                            json={
                                "prompt": "Normalize job titles to Spanish",
                                "few_shots": "[]",
                            },
                            cookies={"sid": sid},
                        )
                        assert response.status_code == 200

                    # 11th request should be rate limited
                    response = test_client.post(
                        "/jobs/review-prompt",
                        json={
                            "prompt": "Normalize job titles to Spanish",
                            "few_shots": "[]",
                        },
                        cookies={"sid": sid},
                    )
                    assert response.status_code == 429

                    # Check error envelope
                    data = response.json()
                    assert "error" in data
                    assert data["error"]["code"] == "rate_limited"
                    assert data["error"]["message"] == "Too many review requests."

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


def test_review_prompt_handles_api_failure_gracefully():
    """Test that review-prompt handles API failures gracefully with error envelope."""
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

                # Mock the anthropic client to raise an exception
                from unittest.mock import patch

                with patch(
                    "app.anthropic.review.review_prompt",
                    side_effect=Exception("Anthropic API failed"),
                ):
                    response = test_client.post(
                        "/jobs/review-prompt",
                        json={
                            "prompt": "Normalize job titles to Spanish",
                            "few_shots": "[]",
                        },
                        cookies={"sid": sid},
                    )
                    assert response.status_code == 500

                    # Check error envelope
                    data = response.json()
                    assert "error" in data
                    assert data["error"]["code"] == "prompt_review_failed"
                    assert "Failed to review prompt" in data["error"]["message"]

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path
