import tempfile
import time

import pytest
import sqlite3

from app.auth.passwords import hash_password
from app.auth.rate_limit import AUTH_LIMITER, COMMIT_LIMITER, GENERAL_LIMITER
from app.db import _apply_migrations
from tests.anthropic.fake_client import FakeAnthropicBatchClient


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """Reset all rate limiters before each test to ensure test isolation."""
    AUTH_LIMITER._hits.clear()
    COMMIT_LIMITER._hits.clear()
    GENERAL_LIMITER._hits.clear()
    yield
    # Clear again after test
    AUTH_LIMITER._hits.clear()
    COMMIT_LIMITER._hits.clear()
    GENERAL_LIMITER._hits.clear()


@pytest.fixture
def conn():
    """Create a fresh in-memory SQLite connection with migrations applied."""
    c = sqlite3.connect(":memory:", isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode = WAL")
    c.execute("PRAGMA foreign_keys = ON")
    _apply_migrations(c)
    yield c
    c.close()


@pytest.fixture
def temp_database():
    """Create a temporary file-based database for tests that need TestClient isolation.
    
    This is needed for tests that use TestClient because TestClient runs requests
    in a separate thread and in-memory databases don't work well with that.
    """
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

            yield db_path

        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


@pytest.fixture
def fake_anthropic() -> FakeAnthropicBatchClient:
    """Provide a fresh fake Anthropic client for testing."""
    return FakeAnthropicBatchClient()


@pytest.fixture
def logged_in_client():
    """Provide an authenticated TestClient with a temporary database.
    
    Each test gets its own isolated database and session.
    """
    test_ip = f"127.0.0.{int(time.time() * 1000) % 254 + 1}"
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
                # Create a TestClient
                from fastapi.testclient import TestClient

                from app.main import create_app

                test_client = TestClient(create_app())

                # Log in to get a session cookie
                auth_response = test_client.post(
                    "/auth", json={"password": correct_password}, headers={"X-Forwarded-For": test_ip}
                )
                assert auth_response.status_code == 200, "Failed to authenticate"
                sid = auth_response.cookies.get("sid")
                assert sid is not None, "Session cookie not set"

                yield test_client, sid

                # Clean up session
                if sid:
                    test_client.post("/auth/logout", cookies={"sid": sid})

            finally:
                # Restore original hash
                app.auth.config.settings.auth_password_hash = original_hash
        finally:
            # Restore original db path
            app.settings.settings.database_path = original_db_path


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Suppress 'no tests collected' exit code (5) during scaffolding phase."""
    if exitstatus == pytest.ExitCode.NO_TESTS_COLLECTED:
        session.exitstatus = pytest.ExitCode.OK
