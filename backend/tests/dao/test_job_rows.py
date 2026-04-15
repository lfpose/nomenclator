import pytest
import time

from app.dao.job_rows import bulk_insert_rows, list_rows, assign_cluster, clear_clusters
from app.dao.jobs import create_job
from app.db import _apply_migrations


@pytest.fixture
def conn():
    """Create a fresh in-memory SQLite connection with migrations applied."""
    import sqlite3
    c = sqlite3.connect(":memory:", isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode = WAL")
    c.execute("PRAGMA foreign_keys = ON")
    _apply_migrations(c)
    yield c
    c.close()


def test_bulk_insert_preserves_row_index_order(conn):
    """Test that bulk_insert_rows preserves row_index order."""
    job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )

    rows = [
        (0, "Ingeniero de Software", "ingeniero de software"),
        (1, "Jefe de Compras", "jefe de compras"),
        (2, "Contador Senior", "contador senior"),
    ]

    bulk_insert_rows(conn, job_id, rows)

    retrieved = list_rows(conn, job_id)
    assert len(retrieved) == 3
    assert retrieved[0].row_index == 0
    assert retrieved[0].original == "Ingeniero de Software"
    assert retrieved[1].row_index == 1
    assert retrieved[1].original == "Jefe de Compras"
    assert retrieved[2].row_index == 2
    assert retrieved[2].original == "Contador Senior"


def test_list_rows_returns_ordered_by_row_index(conn):
    """Test that list_rows returns rows ordered by row_index."""
    job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )

    # Insert rows in non-sequential order
    rows = [
        (5, "Row 5", "row 5"),
        (2, "Row 2", "row 2"),
        (8, "Row 8", "row 8"),
        (1, "Row 1", "row 1"),
    ]

    bulk_insert_rows(conn, job_id, rows)

    retrieved = list_rows(conn, job_id)
    assert len(retrieved) == 4
    # Verify they're ordered by row_index
    assert retrieved[0].row_index == 1
    assert retrieved[1].row_index == 2
    assert retrieved[2].row_index == 5
    assert retrieved[3].row_index == 8


def test_assign_cluster_marks_representative_correctly(conn):
    """Test that assign_cluster marks the representative row correctly."""
    job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )

    rows = [
        (0, "Ingeniero", "ingeniero"),
        (1, "Jefe", "jefe"),
        (2, "Contador", "contador"),
    ]

    bulk_insert_rows(conn, job_id, rows)

    # Create a cluster first (required for foreign key constraint)
    cursor = conn.execute(
        "INSERT INTO clusters (job_id, representative_original, normalized_key, member_count) "
        "VALUES (?, ?, ?, ?)",
        (job_id, "Ingeniero", "ingeniero", 3),
    )
    cluster_id = cursor.lastrowid

    # Get the row IDs
    all_rows = list_rows(conn, job_id)
    row_ids = [r.id for r in all_rows]

    # Assign cluster to all rows, with row 1 as representative
    assign_cluster(conn, row_ids, cluster_id=cluster_id, is_representative_row_id=row_ids[1])

    # Verify cluster assignment
    updated = list_rows(conn, job_id)
    assert all(r.cluster_id == 1 for r in updated)

    # Verify only the representative row is marked
    for row in updated:
        if row.id == row_ids[1]:
            assert row.is_representative is True
        else:
            assert row.is_representative is False


def test_clear_clusters_nulls_cluster_id(conn):
    """Test that clear_clusters nulls cluster_id and clears is_representative."""
    job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )

    rows = [
        (0, "Ingeniero", "ingeniero"),
        (1, "Jefe", "jefe"),
    ]

    bulk_insert_rows(conn, job_id, rows)

    # Create a cluster first (required for foreign key constraint)
    cursor = conn.execute(
        "INSERT INTO clusters (job_id, representative_original, normalized_key, member_count) "
        "VALUES (?, ?, ?, ?)",
        (job_id, "Ingeniero", "ingeniero", 2),
    )
    cluster_id = cursor.lastrowid

    # Get row IDs and assign clusters
    all_rows = list_rows(conn, job_id)
    row_ids = [r.id for r in all_rows]
    assign_cluster(conn, row_ids, cluster_id=cluster_id, is_representative_row_id=row_ids[0])

    # Verify clusters are assigned
    updated = list_rows(conn, job_id)
    assert all(r.cluster_id == 1 for r in updated)

    # Clear clusters
    clear_clusters(conn, job_id)

    # Verify clusters are cleared
    cleared = list_rows(conn, job_id)
    assert all(r.cluster_id is None for r in cleared)
    assert all(r.is_representative is False for r in cleared)


def test_bulk_insert_10000_rows_under_2s(conn):
    """Performance guard: bulk_insert 10000 rows under 2 seconds."""
    job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )

    # Generate 10000 rows
    rows = [
        (i, f"Job Title {i}", f"job title {i}")
        for i in range(10000)
    ]

    start = time.time()
    bulk_insert_rows(conn, job_id, rows)
    elapsed = time.time() - start

    assert elapsed < 2.0, f"Bulk insert took {elapsed:.2f}s, expected < 2s"

    # Verify all rows were inserted
    retrieved = list_rows(conn, job_id)
    assert len(retrieved) == 10000
