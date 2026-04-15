import tempfile

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import app.settings
from app.auth.middleware import require_session
from app.auth.sessions import create_session
from app.db import get_connection


def test_require_session_allows_valid_cookie():
    """Test that valid session cookie allows request to proceed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = f"{tmpdir}/test.db"
        original_path = app.settings.settings.database_path
        app.settings.settings.database_path = db_path

        try:
            # Create and populate the database
            conn = get_connection()
            raw = create_session(conn)
            conn.close()

            fastapi_app = FastAPI()

            @fastapi_app.get("/test")
            def test_route(_=Depends(require_session)):
                return {"status": "ok"}

            client = TestClient(fastapi_app)
            response = client.get("/test", cookies={"sid": raw})
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}
        finally:
            app.settings.settings.database_path = original_path


def test_require_session_raises_on_missing_cookie():
    """Test that missing session cookie returns 401 with error envelope."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = f"{tmpdir}/test.db"
        original_path = app.settings.settings.database_path
        app.settings.settings.database_path = db_path

        try:
            # Create the database
            conn = get_connection()
            conn.close()

            fastapi_app = FastAPI()

            @fastapi_app.get("/test")
            def test_route(_=Depends(require_session)):
                return {"status": "ok"}

            client = TestClient(fastapi_app)
            response = client.get("/test")
            assert response.status_code == 401
            data = response.json()
            assert "error" in data["detail"]
            assert data["detail"]["error"]["code"] == "unauthenticated"
            assert data["detail"]["error"]["message"] == "Session required."
        finally:
            app.settings.settings.database_path = original_path


def test_require_session_raises_on_invalid_cookie():
    """Test that invalid session cookie returns 401 with error envelope."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = f"{tmpdir}/test.db"
        original_path = app.settings.settings.database_path
        app.settings.settings.database_path = db_path

        try:
            # Create the database
            conn = get_connection()
            conn.close()

            fastapi_app = FastAPI()

            @fastapi_app.get("/test")
            def test_route(_=Depends(require_session)):
                return {"status": "ok"}

            client = TestClient(fastapi_app)
            response = client.get("/test", cookies={"sid": "0" * 64})
            assert response.status_code == 401
            data = response.json()
            assert "error" in data["detail"]
            assert data["detail"]["error"]["code"] == "unauthenticated"
            assert data["detail"]["error"]["message"] == "Session required."
        finally:
            app.settings.settings.database_path = original_path


def test_require_session_error_envelope_shape():
    """Test that 401 response has proper error envelope structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = f"{tmpdir}/test.db"
        original_path = app.settings.settings.database_path
        app.settings.settings.database_path = db_path

        try:
            # Create the database
            conn = get_connection()
            conn.close()

            fastapi_app = FastAPI()

            @fastapi_app.get("/test")
            def test_route(_=Depends(require_session)):
                return {"status": "ok"}

            client = TestClient(fastapi_app)
            response = client.get("/test")
            assert response.status_code == 401
            data = response.json()

            # Check top-level structure
            assert isinstance(data, dict)
            assert "detail" in data

            # Check error envelope shape
            detail = data["detail"]
            assert isinstance(detail, dict)
            assert "error" in detail

            error = detail["error"]
            assert isinstance(error, dict)
            assert "code" in error
            assert "message" in error
            assert isinstance(error["code"], str)
            assert isinstance(error["message"], str)
            assert error["code"] == "unauthenticated"
            assert error["message"] == "Session required."
        finally:
            app.settings.settings.database_path = original_path
