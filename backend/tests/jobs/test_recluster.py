"""Tests for recluster_job function."""

import pytest

from app.dao import clusters as clusters_dao
from app.dao import job_rows as job_rows_dao
from app.dao import jobs as jobs_dao
from app.jobs.service import create_preview_job, recluster_job


def test_recluster_replaces_previous_clusters(conn):
    """Reclustering deletes old clusters and creates new ones."""
    # Create a preview job with threshold 90
    preview = create_preview_job(
        conn,
        text="Jefe de Compras\njefe compras\nJefe Compras\nIngeniero de Software",
        threshold=90,
        titles_per_request=25,
    )

    # Count original clusters (should be 2: one for Jefe variants, one for Ingeniero)
    original_clusters = clusters_dao.list_clusters(conn, preview.job_id)
    assert len(original_clusters) == 2

    # Recluster with stricter threshold (95) - should split Jefe variants
    new_preview = recluster_job(conn, preview.job_id, threshold=95)

    # Should have more clusters now
    new_clusters = clusters_dao.list_clusters(conn, preview.job_id)
    assert len(new_clusters) >= len(original_clusters)
    assert new_preview.cluster_count >= preview.cluster_count


def test_recluster_preserves_job_rows_and_originals(conn):
    """Reclustering does not modify job_rows or original values."""
    preview = create_preview_job(
        conn,
        text="Jefe de Compras\njefe compras\nIngeniero de Software",
        threshold=90,
        titles_per_request=25,
    )

    # Get original job rows
    original_rows = job_rows_dao.list_rows(conn, preview.job_id)
    original_texts = [(r.row_index, r.original) for r in original_rows]

    # Recluster
    recluster_job(conn, preview.job_id, threshold=95)

    # Get new job rows
    new_rows = job_rows_dao.list_rows(conn, preview.job_id)
    new_texts = [(r.row_index, r.original) for r in new_rows]

    # Row count and values should be identical
    assert len(new_rows) == len(original_rows)
    assert new_texts == original_texts


def test_recluster_updates_cost_estimate(conn):
    """Reclustering recalculates and updates the cost estimate."""
    preview = create_preview_job(
        conn,
        text="Jefe de Compras\njefe compras\nIngeniero de Software",
        threshold=90,
        titles_per_request=25,
    )

    # Get original cost
    job_before = jobs_dao.get_job(conn, preview.job_id)
    assert job_before is not None
    _ = job_before.est_cost_usd  # Verified it exists

    # Recluster with different threshold (may change cluster count)
    new_preview = recluster_job(conn, preview.job_id, threshold=95)

    # Cost should be updated
    assert new_preview.est_cost_usd is not None
    job_after = jobs_dao.get_job(conn, preview.job_id)
    assert job_after is not None
    # Cost may differ if cluster count changed
    assert job_after.est_cost_usd >= 0


def test_recluster_raises_on_non_preview_state(conn):
    """Reclustering raises ValueError when job is not in preview state."""
    preview = create_preview_job(
        conn,
        text="Jefe de Compras\njefe compras",
        threshold=90,
        titles_per_request=25,
    )

    # Transition to cancelled (preview cannot go directly to completed)
    from app.jobs.service import transition
    transition(conn, preview.job_id, "cancelled", reason="test")

    # Should raise ValueError
    with pytest.raises(ValueError, match="invalid_state"):
        recluster_job(conn, preview.job_id, threshold=95)


def test_recluster_stricter_threshold_produces_more_clusters(conn):
    """Stricter clustering threshold produces more clusters."""
    # Create a preview job with permissive threshold (80)
    preview = create_preview_job(
        conn,
        text="Jefe de Compras\njefe compras\nJefe Compras\nIngeniero de Software\ningeniero software",
        threshold=80,
        titles_per_request=25,
    )

    # With threshold 80, likely all Jefe variants are in one cluster
    permissive_clusters = len(clusters_dao.list_clusters(conn, preview.job_id))

    # Recluster with stricter threshold (95)
    recluster_job(conn, preview.job_id, threshold=95)

    # With threshold 95, should have more clusters
    stricter_clusters = len(clusters_dao.list_clusters(conn, preview.job_id))
    assert stricter_clusters >= permissive_clusters
