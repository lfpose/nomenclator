"""Tests for job cost estimator."""

from app.jobs.estimator import estimate_job_cost
from app.pricing import estimate_cost as pricing_estimate_cost


def test_estimate_job_cost_delegates_to_pricing() -> None:
    """Verify that estimate_job_cost delegates to pricing.estimate_cost."""
    # Use the real pricing function to verify delegation
    cluster_count = 100
    titles_per_request = 10

    result = estimate_job_cost(cluster_count, titles_per_request)
    expected = pricing_estimate_cost(cluster_count, titles_per_request)

    assert result == expected


def test_estimate_job_cost_zero_clusters_is_zero() -> None:
    """Verify that zero clusters returns zero cost."""
    result = estimate_job_cost(0, 10)
    assert result == 0.0

    # Also test negative cluster count
    result = estimate_job_cost(-5, 10)
    assert result == 0.0
