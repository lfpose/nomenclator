import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from ..db import db_dep
from ..settings import settings

router = APIRouter()  # No auth required


@router.get("")
def health(request: Request, conn=Depends(db_dep)):
    """Health check endpoint.

    Returns the health status of the application including database
    connectivity and worker heartbeat. No authentication required.
    """
    try:
        conn.execute("SELECT 1").fetchone()
        db_ok = "ok"
    except Exception:
        db_ok = "error"

    worker = getattr(request.app.state, "worker", None)
    heartbeat = worker.last_tick_at if worker else 0
    seconds_ago = time.time() - heartbeat if heartbeat else None

    ok = db_ok == "ok" and (seconds_ago is None or seconds_ago < 120)

    return {
        "ok": ok,
        "db": db_ok,
        "worker_heartbeat": (
            datetime.fromtimestamp(heartbeat, tz=timezone.utc).isoformat() if heartbeat else None
        ),
        "worker_last_tick_seconds_ago": seconds_ago,
        "version": settings.version,
    }
