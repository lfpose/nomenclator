from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from ..auth.middleware import require_session
from ..db import db_dep
from ..jobs.estimator import check_cap

router = APIRouter(dependencies=[Depends(require_session)])


@router.get("")
def spend(conn=Depends(db_dep)):
    """Get current spend information including usage and cap.

    Returns the rolling 30-day spend, monthly cap, and reset date.
    """
    cap = check_cap(conn, estimated_usd=0.0)
    return {
        "used_usd": round(cap.used_usd, 4),
        "cap_usd": cap.cap_usd,
        "window_days": 30,
        "reset_date": (
            datetime.fromtimestamp(cap.reset_date_unix, tz=timezone.utc)
            .date()
            .isoformat()
            if cap.reset_date_unix
            else None
        ),
    }
