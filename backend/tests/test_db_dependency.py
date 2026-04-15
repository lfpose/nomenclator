import tempfile
import unittest.mock as mock

from fastapi import Depends
from fastapi.testclient import TestClient

from app.db import db_dep, get_connection
from app.main import create_app


class ConnectionWrapper:
    """Wrapper around sqlite3.Connection that tracks close calls."""
    def __init__(self, conn):
        self._conn = conn
        self.close_called = False
    
    def __getattr__(self, name):
        return getattr(self._conn, name)
    
    def close(self):
        self.close_called = True
        self._conn.close()


def test_db_dep_yields_working_connection():
    """Test that db_dep yields a working connection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = f"{tmpdir}/test.db"
        import app.settings
        original_path = app.settings.settings.database_path
        app.settings.settings.database_path = db_path

        try:
            fastapi_app = create_app()

            @fastapi_app.get("/test-db")
            def test_db_route(conn=Depends(db_dep)):
                result = conn.execute("SELECT 1").fetchone()
                return {"result": result[0]}

            client = TestClient(fastapi_app)
            response = client.get("/test-db")
            assert response.status_code == 200
            assert response.json() == {"result": 1}
        finally:
            app.settings.settings.database_path = original_path


def test_db_dep_closes_on_exception():
    """Test that db_dep closes the connection even if an exception occurs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = f"{tmpdir}/test.db"
        import app.settings
        original_path = app.settings.settings.database_path
        app.settings.settings.database_path = db_path

        try:
            fastapi_app = create_app()

            # Track the wrapped connection
            wrapper_ref = []

            def wrapped_get_connection():
                conn = get_connection()
                wrapper = ConnectionWrapper(conn)
                wrapper_ref.append(wrapper)
                return wrapper

            with mock.patch("app.db.get_connection", side_effect=wrapped_get_connection):
                @fastapi_app.get("/test-exception")
                def test_exception_route(conn=Depends(db_dep)):
                    raise ValueError("Test exception")

                client = TestClient(fastapi_app, raise_server_exceptions=False)
                response = client.get("/test-exception")
                assert response.status_code == 500

                # Verify close was called on the wrapped connection
                assert len(wrapper_ref) == 1
                assert wrapper_ref[0].close_called is True
        finally:
            app.settings.settings.database_path = original_path
