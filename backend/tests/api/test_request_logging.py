"""Tests for HTTP request logging middleware."""

import pytest
from fastapi.testclient import TestClient
from app.main import create_app


def test_logs_contain_method_path_status(caplog):
    """Verify logs contain method, path, status, and duration."""
    caplog.set_level("INFO", logger="nomenclator.http")

    client = TestClient(create_app())
    response = client.get("/health")

    assert response.status_code == 200

    # Check that a log entry was created
    assert len(caplog.records) > 0

    # Find the http.request log entry
    http_logs = [r for r in caplog.records if r.name == "nomenclator.http" and r.message == "http.request"]
    assert len(http_logs) > 0

    log_entry = http_logs[0]

    # Verify expected fields are present
    assert hasattr(log_entry, "method")
    assert hasattr(log_entry, "path")
    assert hasattr(log_entry, "status")
    assert hasattr(log_entry, "duration_ms")

    # Verify values are correct for /health request
    assert log_entry.method == "GET"
    assert log_entry.path == "/health"
    assert log_entry.status == 200
    assert log_entry.duration_ms >= 0
