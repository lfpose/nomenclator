import logging
import traceback

from fastapi.responses import JSONResponse

from ..settings import settings

log = logging.getLogger("nomenclator.api")


def _dev_mode() -> bool:
    return settings.debug


class APIError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, details: dict | None = None):
        self.code = code
        self.message = message
        self.status = status
        self.details = details or {}


def error_response(code: str, message: str, status: int, details: dict | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details or {}}},
    )


def register_handlers(app):
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    @app.exception_handler(APIError)
    async def _api(req, exc):
        log.warning(
            "APIError %s %s -> %s %s: %s",
            req.method,
            req.url.path,
            exc.status,
            exc.code,
            exc.message,
        )
        return error_response(exc.code, exc.message, exc.status, exc.details)

    @app.exception_handler(StarletteHTTPException)
    async def _http(req, exc):
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return error_response("http_error", str(exc.detail), exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _val(req, exc):
        return error_response("bad_request", "Invalid request body", 400, {"errors": exc.errors()})

    @app.exception_handler(Exception)
    async def _unknown(req, exc):
        # Always log full traceback so the operator can diagnose 500s.
        log.exception("Unhandled exception on %s %s", req.method, req.url.path)
        details: dict = {"path": str(req.url.path)}
        # In dev mode, propagate the exception type + message + short traceback to
        # the client so the ErrorModal can surface what actually broke.
        if _dev_mode():
            details["exception_type"] = type(exc).__name__
            details["exception_message"] = str(exc)
            details["traceback"] = "".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            )[-2000:]
        return error_response(
            "internal_error", "An unexpected error occurred.", 500, details
        )
