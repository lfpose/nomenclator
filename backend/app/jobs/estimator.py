"""Cost estimation helpers for jobs."""

import time
from dataclasses import dataclass

from ..dao.spend_log import insert_spend, reset_date_approx, sum_last_30_days
from ..pricing import (
    HAIKU_BATCH_IN_USD_PER_MTOK,
    HAIKU_BATCH_OUT_USD_PER_MTOK,
    MONTHLY_SPEND_CAP_USD,
    estimate_cost,
)


def estimate_job_cost(cluster_count: int, titles_per_request: int) -> float:
    """Estimate cost for a job given cluster count and titles per request.

    This is a thin wrapper around pricing.estimate_cost for discoverability
    within the jobs namespace.

    Args:
        cluster_count: Number of unique clusters to process
        titles_per_request: Number of titles per batch request

    Returns:
        Estimated cost in USD
    """
    return estimate_cost(cluster_count, titles_per_request)


@dataclass(frozen=True)
class CapCheckResult:
    """Result of a spend cap check.

    Attributes:
        ok: Whether the estimated cost is within the monthly cap
        used_usd: Total USD spent in the last 30 days
        estimated_usd: Estimated cost for the new job/batch
        cap_usd: Monthly spend cap in USD
        reset_date_unix: Unix timestamp when the 30-day window will roll over,
            or None if no spend entries exist
    """
    ok: bool
    used_usd: float
    estimated_usd: float
    cap_usd: float
    reset_date_unix: int | None


def check_cap(
    conn,
    estimated_usd: float,
    *,
    now: int | None = None,
    is_dry_run: bool = False,
) -> CapCheckResult:
    """Check whether an estimated cost exceeds the monthly spend cap.

    Args:
        conn: Database connection
        estimated_usd: Estimated cost for the new job/batch
        now: Current Unix timestamp (defaults to current time)
        is_dry_run: If True, skip the cap check and return ok=True

    Returns:
        CapCheckResult with the check outcome and spending details

    Note:
        Dry-run jobs skip the cap check entirely — is_dry_run=True returns
        ok=True regardless of spend level, with $0 cost figures.
    """
    if is_dry_run:
        return CapCheckResult(
            ok=True,
            used_usd=0.0,
            estimated_usd=0.0,
            cap_usd=MONTHLY_SPEND_CAP_USD,
            reset_date_unix=None,
        )

    used = sum_last_30_days(conn, now)
    ok = (used + estimated_usd) <= MONTHLY_SPEND_CAP_USD
    reset = reset_date_approx(conn, now)

    return CapCheckResult(
        ok=ok,
        used_usd=used,
        estimated_usd=estimated_usd,
        cap_usd=MONTHLY_SPEND_CAP_USD,
        reset_date_unix=reset,
    )


def record_actual_spend(
    conn,
    *,
    job_id: str,
    batch_id: str | None,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Record actual spend from Anthropic batch API response.

    Computes USD from input and output token counts and inserts
    a spend log entry.

    Args:
        conn: Database connection
        job_id: Job ID
        batch_id: Optional batch ID (None for jobs with no batch,
            e.g. during testing)
        input_tokens: Number of input tokens consumed
        output_tokens: Number of output tokens consumed

    Returns:
        The computed USD amount
    """
    usd = (
        input_tokens / 1_000_000 * HAIKU_BATCH_IN_USD_PER_MTOK
        + output_tokens / 1_000_000 * HAIKU_BATCH_OUT_USD_PER_MTOK
    )
    insert_spend(conn, job_id=job_id, batch_id=batch_id, usd=usd, at=int(time.time()))
    return usd
