import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware

log = logging.getLogger("nomenclator.http")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs HTTP requests with method, path, status, and duration."""

    async def dispatch(self, request, call_next):
        start = time.time()
        response = await call_next(request)
        duration_ms = int((time.time() - start) * 1000)

        log.info(
            "http.request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        return response
