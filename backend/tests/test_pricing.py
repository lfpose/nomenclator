"""Tests for pricing and cost estimation."""

from app.pricing import estimate_cost


def test_estimate_cost_zero_clusters_returns_zero() -> None:
    """Zero clusters should return zero cost."""
    assert estimate_cost(0, 10) == 0.0
    assert estimate_cost(0, 25) == 0.0


def test_estimate_cost_2500_clusters_25_tpr_within_range() -> None:
    """2500 clusters with 25 titles per request should cost between $0.25 and $0.50."""
    cost = estimate_cost(2500, 25)
    assert 0.25 <= cost <= 0.50


def test_estimate_cost_monotonic_in_cluster_count() -> None:
    """Cost should increase monotonically with cluster count (fixed TPR)."""
    cost_100 = estimate_cost(100, 10)
    cost_500 = estimate_cost(500, 10)
    cost_1000 = estimate_cost(1000, 10)
    assert cost_1000 > cost_500 > cost_100


def test_estimate_cost_decreases_when_tpr_increases() -> None:
    """Cost should decrease when titles per request increases (fixed cluster count)."""
    cost_tpr_10 = estimate_cost(1000, 10)
    cost_tpr_25 = estimate_cost(1000, 25)
    cost_tpr_50 = estimate_cost(1000, 50)
    assert cost_tpr_10 > cost_tpr_25 > cost_tpr_50
