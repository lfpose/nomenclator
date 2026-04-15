from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_200():
    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_health_reports_version():
    client = TestClient(create_app())
    r = client.get("/health")
    assert "version" in r.json()
