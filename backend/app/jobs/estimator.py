"""Cost estimation helpers for jobs."""

from ..pricing import estimate_cost


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
