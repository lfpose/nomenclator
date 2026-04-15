from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from ..auth.config import get_password_hash
from ..auth.middleware import require_session
from ..auth.passwords import verify_password
from ..auth.rate_limit import AUTH_LIMITER
from ..auth.sessions import create_session, destroy_session
from ..db import db_dep
from .errors import APIError

router = APIRouter()


class AuthRequest(BaseModel):
    password: str


@router.post("/auth")
def auth_login(
    body: AuthRequest, request: Request, response: Response, conn=Depends(db_dep)
):
    # Use X-Forwarded-For header if present (for testing), otherwise use client.host
    ip = request.headers.get("X-Forwarded-For", request.client.host or "unknown")
    if not AUTH_LIMITER.allow(ip):
        raise APIError("rate_limited", "Too many attempts.", 429)
    if not verify_password(get_password_hash(), body.password):
        raise APIError("unauthenticated", "Wrong password.", 401)

    sid = create_session(conn)
    response.set_cookie(
        "sid",
        sid,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=2592000,
        path="/",
    )
    return {"ok": True}


@router.get("/me", dependencies=[Depends(require_session)])
def me():
    return {"authenticated": True}


@router.post("/auth/logout", dependencies=[Depends(require_session)])
def logout(request: Request, response: Response, conn=Depends(db_dep)):
    raw = request.cookies.get("sid")
    if raw:
        destroy_session(conn, raw)
    response.delete_cookie("sid", path="/")
    return {"ok": True}
