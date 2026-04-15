from fastapi import Depends, HTTPException, Request

from ..db import db_dep
from .sessions import validate_session


def require_session(request: Request, conn=Depends(db_dep)) -> None:
    """FastAPI dependency that validates session from cookie.

    Raises HTTPException 401 if session is missing or invalid.
    """
    raw = request.cookies.get("sid")
    if not validate_session(conn, raw):
        raise HTTPException(
            status_code=401,
            detail={
                "error": {"code": "unauthenticated", "message": "Session required."}
            },
        )
