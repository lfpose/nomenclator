"""Tests for create_preview_job function."""

import pytest

from app.csv_io.ingest import CSVError
from app.dao import clusters as clusters_dao
from app.dao import job_rows as job_rows_dao
from app.dao import jobs as jobs_dao
from app.jobs.service import create_preview_job


def test_preview_creates_job_with_status_preview(conn) -> None:
    """Verify that a job is created with status 'preview'."""
    csv_bytes = b"Jefe de Compras\nJefe de Ventas\nDirector de Marketing"
    result = create_preview_job(
        conn,
        file_bytes=csv_bytes,
        threshold=90,
        titles_per_request=25,
    )

    job = jobs_dao.get_job(conn, result.job_id)
    assert job is not None
    assert job.status == "preview"
    assert job.fuzzy_threshold == 90
    assert job.titles_per_request == 25


def test_preview_writes_all_job_rows(conn) -> None:
    """Verify that all input rows are written to job_rows."""
    csv_bytes = b"Jefe de Compras\nJefe de Ventas\nDirector de Marketing\nIngeniero de Software"
    result = create_preview_job(
        conn,
        file_bytes=csv_bytes,
        threshold=90,
        titles_per_request=25,
    )

    rows = job_rows_dao.list_rows(conn, result.job_id)
    assert len(rows) == 4
    assert rows[0].original == "Jefe de Compras"
    assert rows[1].original == "Jefe de Ventas"
    assert rows[2].original == "Director de Marketing"
    assert rows[3].original == "Ingeniero de Software"


def test_preview_writes_clusters_with_representatives(conn) -> None:
    """Verify that clusters are written with representative_original values."""
    # Create input that will cluster (similar titles)
    csv_bytes = b"Jefe de Compras\nJefe Compras\njefe de compras\nJefe de Ventas\nDirector IT"
    result = create_preview_job(
        conn,
        file_bytes=csv_bytes,
        threshold=90,
        titles_per_request=25,
    )

    clusters = clusters_dao.list_clusters(conn, result.job_id)
    assert len(clusters) >= 2  # At least 2 clusters (jefe de compras variants, others)
    for cluster in clusters:
        assert cluster.representative_original is not None
        assert cluster.normalized_key is not None
        assert cluster.member_count >= 1


def test_preview_assigns_cluster_id_to_every_row(conn) -> None:
    """Verify that every row gets a cluster_id assigned."""
    csv_bytes = b"Jefe de Compras\nJefe de Ventas\nDirector IT"
    result = create_preview_job(
        conn,
        file_bytes=csv_bytes,
        threshold=90,
        titles_per_request=25,
    )

    rows = job_rows_dao.list_rows(conn, result.job_id)
    assert all(r.cluster_id is not None for r in rows), "All rows should have a cluster_id"
    # At least one row should be marked as representative
    assert any(r.is_representative for r in rows), "At least one row should be a representative"


def test_preview_computes_cost_estimate(conn) -> None:
    """Verify that cost estimate is computed correctly."""
    csv_bytes = b"Jefe de Compras\nJefe de Ventas\nDirector IT"
    result = create_preview_job(
        conn,
        file_bytes=csv_bytes,
        threshold=90,
        titles_per_request=25,
    )

    assert result.est_cost_usd > 0
    assert result.est_cost_usd < 1.0  # Should be a small amount for 3 rows

    # Verify it's also stored on the job
    job = jobs_dao.get_job(conn, result.job_id)
    assert job is not None
    assert job.est_cost_usd == result.est_cost_usd


def test_preview_returns_top_10_largest_clusters(conn) -> None:
    """Verify that top 10 largest clusters are returned."""
    # Create a diverse input with multiple clusters
    titles = []
    # Create 15 clusters with varying sizes
    for i in range(15):
        size = i + 1  # Sizes 1-15
        for j in range(size):
            titles.append(f"Job Title {i:02d} Variant {j:02d}")

    csv_bytes = "\n".join(titles).encode()
    result = create_preview_job(
        conn,
        file_bytes=csv_bytes,
        threshold=90,
        titles_per_request=25,
    )

    # Should return at most 10 clusters
    assert len(result.top_clusters) <= 10

    # Should be sorted by member_count descending
    if len(result.top_clusters) > 1:
        for i in range(len(result.top_clusters) - 1):
            assert (
                result.top_clusters[i]["member_count"]
                >= result.top_clusters[i + 1]["member_count"]
            )

    # Each cluster should have required fields
    for cluster in result.top_clusters:
        assert "representative" in cluster
        assert "member_count" in cluster
        assert "members" in cluster
        assert len(cluster["members"]) == cluster["member_count"]


def test_preview_emits_large_cluster_warning_above_50(conn) -> None:
    """Verify that warnings are emitted for clusters larger than 50 members."""
    # Create a cluster with 51 identical titles
    titles = ["Jefe de Compras"] * 51
    titles.append("Jefe de Ventas")  # Add one different title

    csv_bytes = "\n".join(titles).encode()
    result = create_preview_job(
        conn,
        file_bytes=csv_bytes,
        threshold=90,
        titles_per_request=25,
    )

    # Should have a large_cluster warning
    assert len(result.warnings) > 0
    large_cluster_warnings = [w for w in result.warnings if w["type"] == "large_cluster"]
    assert len(large_cluster_warnings) > 0

    warning = large_cluster_warnings[0]
    assert warning["type"] == "large_cluster"
    assert "cluster_id" in warning
    assert "representative" in warning
    assert warning["member_count"] >= 50


def test_preview_propagates_ingest_errors(conn) -> None:
    """Verify that ingest errors are propagated correctly."""
    # Test with row that normalizes to empty (should raise CSVError)
    csv_bytes = b"Jefe de Compras\n!!!\nJefe de Ventas"  # "!!!" normalizes to empty

    with pytest.raises(CSVError) as exc_info:
        create_preview_job(
            conn,
            file_bytes=csv_bytes,
            threshold=90,
            titles_per_request=25,
        )

    assert exc_info.value.code == "input_contains_blank_rows"

    # Test with neither file_bytes nor text
    with pytest.raises(CSVError) as exc_info2:
        create_preview_job(
            conn,
            file_bytes=None,
            text=None,
            threshold=90,
            titles_per_request=25,
        )
    assert exc_info2.value.code == "input_malformed"
