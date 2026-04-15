from fastapi.testclient import TestClient
from app.api.errors import APIError, register_handlers
from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel, Field


def test_api_error_produces_envelope():
    """Verify APIError produces correct error envelope."""
    app = FastAPI()
    register_handlers(app)

    @app.get("/test-api-error")
    def test_api_error():
        raise APIError("test_code", "Test message", 422, {"extra": "info"})

    with TestClient(app) as client:
        response = client.get("/test-api-error")
        assert response.status_code == 422
        assert response.json() == {
            "error": {
                "code": "test_code",
                "message": "Test message",
                "details": {"extra": "info"}
            }
        }


def test_http_exception_produces_envelope():
    """Verify HTTPException produces correct error envelope."""
    app = FastAPI()
    register_handlers(app)

    @app.get("/test-http-exception")
    def test_http_exception():
        raise StarletteHTTPException(status_code=403, detail="Forbidden")

    with TestClient(app) as client:
        response = client.get("/test-http-exception")
        assert response.status_code == 403
        assert response.json() == {
            "error": {
                "code": "http_error",
                "message": "Forbidden",
                "details": {}
            }
        }


def test_http_exception_with_existing_envelope():
    """Verify HTTPException with existing error envelope is passed through."""
    app = FastAPI()
    register_handlers(app)

    @app.get("/test-http-envelope")
    def test_http_envelope():
        raise StarletteHTTPException(
            status_code=401,
            detail={"error": {"code": "custom_code", "message": "Custom error", "details": {}}}
        )

    with TestClient(app) as client:
        response = client.get("/test-http-envelope")
        assert response.status_code == 401
        assert response.json() == {
            "error": {
                "code": "custom_code",
                "message": "Custom error",
                "details": {}
            }
        }


def test_validation_error_produces_bad_request():
    """Verify RequestValidationError produces bad_request envelope."""
    app = FastAPI()
    register_handlers(app)

    class TestModel(BaseModel):
        name: str = Field(..., min_length=1)

    @app.post("/test-validation")
    def test_validation(body: TestModel):
        return body

    with TestClient(app) as client:
        response = client.post("/test-validation", json={"name": ""})
        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "bad_request"
        assert data["error"]["message"] == "Invalid request body"
        assert "errors" in data["error"]["details"]
        assert len(data["error"]["details"]["errors"]) > 0


def test_unknown_exception_produces_internal_error():
    """Verify unknown exception produces internal_error envelope."""
    app = FastAPI()
    register_handlers(app)

    @app.get("/test-unknown-error")
    def test_unknown_error():
        raise ValueError("Something went wrong")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/test-unknown-error")
        assert response.status_code == 500
        assert response.json() == {
            "error": {
                "code": "internal_error",
                "message": "An unexpected error occurred.",
                "details": {}
            }
        }
