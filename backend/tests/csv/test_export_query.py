import pytest
from backend.app.csv_io.exporter import fetch_export_rows, ExportRow


def test_export_rows_in_row_index_order(conn):
    """Verifies rows are returned in row_index order."""
    # Create job and rows
    conn.execute(
        "INSERT INTO jobs (id, status, total_rows, task_template_id, created_at) VALUES (?, ?, ?, ?, ?)",
        ("job-1", "completed", 3, "job_titles_es", 1234567890),
    )
    conn.execute(
        "INSERT INTO job_rows (job_id, row_index, original, normalized) VALUES (?, ?, ?, ?)",
        ("job-1", 2, "row-2", "row-2"),
    )
    conn.execute(
        "INSERT INTO job_rows (job_id, row_index, original, normalized) VALUES (?, ?, ?, ?)",
        ("job-1", 0, "row-0", "row-0"),
    )
    conn.execute(
        "INSERT INTO job_rows (job_id, row_index, original, normalized) VALUES (?, ?, ?, ?)",
        ("job-1", 1, "row-1", "row-1"),
    )
    conn.commit()

    rows = fetch_export_rows(conn, "job-1")
    assert len(rows) == 3
    assert rows[0].original == "row-0"
    assert rows[1].original == "row-1"
    assert rows[2].original == "row-2"


def test_export_populated_row_has_answers(conn):
    """Verifies a row with a populated cluster has answers."""
    # Create job, cluster, and row
    conn.execute(
        "INSERT INTO jobs (id, status, total_rows, task_template_id, created_at) VALUES (?, ?, ?, ?, ?)",
        ("job-1", "completed", 1, "job_titles_es", 1234567890),
    )
    conn.execute(
        "INSERT INTO clusters (job_id, representative_original, normalized_key, member_count, male_es, female_es, category) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("job-1", "jefe compras", "jefe compras", 1, "Jefe de Compras", "Jefa de Compras", "Supply Chain"),
    )
    cluster_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO job_rows (job_id, row_index, original, normalized, cluster_id) VALUES (?, ?, ?, ?, ?)",
        ("job-1", 0, "jefe compras", "jefe compras", cluster_id),
    )
    conn.commit()

    rows = fetch_export_rows(conn, "job-1")
    assert len(rows) == 1
    assert rows[0].original == "jefe compras"
    assert rows[0].male_es == "Jefe de Compras"
    assert rows[0].female_es == "Jefa de Compras"
    assert rows[0].category == "Supply Chain"
    assert rows[0].error == ""


def test_export_unresolved_cluster_returns_empty_answers(conn):
    """Verifies a row with an unresolved cluster returns empty answers."""
    # Create job, cluster without answers, and row
    conn.execute(
        "INSERT INTO jobs (id, status, total_rows, task_template_id, created_at) VALUES (?, ?, ?, ?, ?)",
        ("job-1", "completed", 1, "job_titles_es", 1234567890),
    )
    conn.execute(
        "INSERT INTO clusters (job_id, representative_original, normalized_key, member_count) VALUES (?, ?, ?, ?)",
        ("job-1", "jefe compras", "jefe compras", 1),
    )
    cluster_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO job_rows (job_id, row_index, original, normalized, cluster_id) VALUES (?, ?, ?, ?, ?)",
        ("job-1", 0, "jefe compras", "jefe compras", cluster_id),
    )
    conn.commit()

    rows = fetch_export_rows(conn, "job-1")
    assert len(rows) == 1
    assert rows[0].original == "jefe compras"
    assert rows[0].male_es == ""
    assert rows[0].female_es == ""
    assert rows[0].category == ""
    assert rows[0].error == ""


def test_export_errored_cluster_returns_error_code(conn):
    """Verifies a row with an errored cluster returns the error code."""
    # Create job, cluster with error, and row
    conn.execute(
        "INSERT INTO jobs (id, status, total_rows, task_template_id, created_at) VALUES (?, ?, ?, ?, ?)",
        ("job-1", "completed", 1, "job_titles_es", 1234567890),
    )
    conn.execute(
        "INSERT INTO clusters (job_id, representative_original, normalized_key, member_count, error) VALUES (?, ?, ?, ?, ?)",
        ("job-1", "jefe compras", "jefe compras", 1, "max_retries_exceeded"),
    )
    cluster_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO job_rows (job_id, row_index, original, normalized, cluster_id) VALUES (?, ?, ?, ?, ?)",
        ("job-1", 0, "jefe compras", "jefe compras", cluster_id),
    )
    conn.commit()

    rows = fetch_export_rows(conn, "job-1")
    assert len(rows) == 1
    assert rows[0].original == "jefe compras"
    assert rows[0].male_es == ""
    assert rows[0].female_es == ""
    assert rows[0].category == ""
    assert rows[0].error == "max_retries_exceeded"


def test_export_missing_cluster_id_returns_empty_row_not_dropped(conn):
    """Verifies a row with NULL cluster_id still appears with 4 empty strings."""
    # Create job and row without cluster
    conn.execute(
        "INSERT INTO jobs (id, status, total_rows, task_template_id, created_at) VALUES (?, ?, ?, ?, ?)",
        ("job-1", "completed", 1, "job_titles_es", 1234567890),
    )
    conn.execute(
        "INSERT INTO job_rows (job_id, row_index, original, normalized) VALUES (?, ?, ?, ?)",
        ("job-1", 0, "jefe compras", "jefe compras"),
    )
    conn.commit()

    rows = fetch_export_rows(conn, "job-1")
    assert len(rows) == 1
    assert rows[0].original == "jefe compras"
    assert rows[0].male_es == ""
    assert rows[0].female_es == ""
    assert rows[0].category == ""
    assert rows[0].error == ""
