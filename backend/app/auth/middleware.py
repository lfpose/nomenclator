from fastapi import Depends, HTTPException, Request

from ..api.errors import APIError
from ..db import db_dep
from .rate_limit import GENERAL_LIMITER
from .sessions import validate_session


def require_session(request: Request, conn=Depends(db_dep)) -> None:
    """FastAPI dependency that validates session from cookie and applies general rate limit.

    Raises HTTPException 401 if session is missing or invalid.
    Raises APIError 429 if rate limit is exceeded.
    """
    raw = request.cookies.get("sid")
    if not validate_session(conn, raw):
        raise HTTPException(
            status_code=401,
            detail={
                "error": {"code": "unauthenticated", "message": "Session required."}
            },
        )
    if raw and not GENERAL_LIMITER.allow(raw):
        raise APIError("rate_limited", "Too many requests.", 429)
