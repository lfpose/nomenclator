"""Tests for GET /health endpoint."""

import pytest
from fastapi.testclient import TestClient
from app.main import create_app


@pytest.fixture
def client(temp_database):
    """Create a TestClient with a temporary database."""
    return TestClient(create_app())


def test_health_returns_200(client):
    """Verify health endpoint returns 200."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_reports_db_ok(client):
    """Verify health endpoint reports database status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "db" in data
    assert data["db"] in ("ok", "error")


def test_health_reports_worker_heartbeat_when_set(temp_database):
    """Verify health endpoint reports worker heartbeat when worker exists."""
    from app.main import create_app
    from app.worker.poller import Worker
    from tests.anthropic.fake_client import FakeAnthropicBatchClient
    from app.db import get_connection

    app = create_app()
    fake_client = FakeAnthropicBatchClient()
    worker = Worker(client=fake_client, db_factory=get_connection)
    worker.last_tick_at = 1234567890.0  # Set a heartbeat
    app.state.worker = worker

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "worker_heartbeat" in data
    assert data["worker_heartbeat"] is not None
    assert "worker_last_tick_seconds_ago" in data
    assert data["worker_last_tick_seconds_ago"] is not None


def test_health_no_auth_required(client):
    """Verify health endpoint does not require authentication."""
    response = client.get("/health")
    # Should not return 401 unauthenticated error
    assert response.status_code == 200
