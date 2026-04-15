import pytest
from backend.app.csv_io.exporter import export_job_to_csv, RowCountDriftError, write_csv_bytes, ExportRow


def test_export_happy_path_bytes_nonzero(conn):
    """Verifies export returns nonzero bytes for a happy path job."""
    # Create job with rows and clusters
    conn.execute(
        "INSERT INTO jobs (id, status, total_rows, task_template_id, created_at) VALUES (?, ?, ?, ?, ?)",
        ("job-1", "completed", 2, "job_titles_es", 1234567890),
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
    conn.execute(
        "INSERT INTO job_rows (job_id, row_index, original, normalized, cluster_id) VALUES (?, ?, ?, ?, ?)",
        ("job-1", 1, "ingeniero software", "ingeniero software", cluster_id),
    )
    conn.commit()

    output = export_job_to_csv(conn, "job-1")
    assert isinstance(output, bytes)
    assert len(output) > 0
    # Check it starts with BOM
    assert output.startswith(b"\xef\xbb\xbf")


def test_export_row_count_matches_input(conn):
    """Verifies export returns rows matching job.total_rows count."""
    # Create job with 3 rows
    conn.execute(
        "INSERT INTO jobs (id, status, total_rows, task_template_id, created_at) VALUES (?, ?, ?, ?, ?)",
        ("job-1", "completed", 3, "job_titles_es", 1234567890),
    )
    conn.execute(
        "INSERT INTO clusters (job_id, representative_original, normalized_key, member_count, male_es, female_es, category) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("job-1", "jefe compras", "jefe compras", 3, "Jefe de Compras", "Jefa de Compras", "Supply Chain"),
    )
    cluster_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO job_rows (job_id, row_index, original, normalized, cluster_id) VALUES (?, ?, ?, ?, ?)",
        ("job-1", 0, "row1", "row1", cluster_id),
    )
    conn.execute(
        "INSERT INTO job_rows (job_id, row_index, original, normalized, cluster_id) VALUES (?, ?, ?, ?, ?)",
        ("job-1", 1, "row2", "row2", cluster_id),
    )
    conn.execute(
        "INSERT INTO job_rows (job_id, row_index, original, normalized, cluster_id) VALUES (?, ?, ?, ?, ?)",
        ("job-1", 2, "row3", "row3", cluster_id),
    )
    conn.commit()

    output = export_job_to_csv(conn, "job-1")
    # Output should have BOM + header + 3 data rows
    output_str = output[3:].decode("utf-8")
    lines = output_str.split("\r\n")
    # Header + 3 data rows = 4 lines (last line is empty due to trailing \r\n)
    assert len([l for l in lines if l]) == 4  # 1 header + 3 data rows


def test_export_raises_on_count_drift(conn):
    """Verifies RowCountDriftError is raised when row count doesn't match job.total_rows."""
    # Create job with total_rows=10 but only insert 3 rows
    conn.execute(
        "INSERT INTO jobs (id, status, total_rows, task_template_id, created_at) VALUES (?, ?, ?, ?, ?)",
        ("job-1", "completed", 10, "job_titles_es", 1234567890),
    )
    conn.execute(
        "INSERT INTO clusters (job_id, representative_original, normalized_key, member_count, male_es, female_es, category) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("job-1", "jefe compras", "jefe compras", 3, "Jefe de Compras", "Jefa de Compras", "Supply Chain"),
    )
    cluster_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO job_rows (job_id, row_index, original, normalized, cluster_id) VALUES (?, ?, ?, ?, ?)",
        ("job-1", 0, "row1", "row1", cluster_id),
    )
    conn.execute(
        "INSERT INTO job_rows (job_id, row_index, original, normalized, cluster_id) VALUES (?, ?, ?, ?, ?)",
        ("job-1", 1, "row2", "row2", cluster_id),
    )
    conn.execute(
        "INSERT INTO job_rows (job_id, row_index, original, normalized, cluster_id) VALUES (?, ?, ?, ?, ?)",
        ("job-1", 2, "row3", "row3", cluster_id),
    )
    conn.commit()

    with pytest.raises(RowCountDriftError) as exc_info:
        export_job_to_csv(conn, "job-1")

    error = exc_info.value
    assert error.job_id == "job-1"
    assert error.in_count == 10
    assert error.out_count == 3


def test_export_drift_logged_with_counts(conn, caplog):
    """Verifies drift is logged with job_id and counts."""
    # Create job with total_rows=5 but only insert 2 rows
    conn.execute(
        "INSERT INTO jobs (id, status, total_rows, task_template_id, created_at) VALUES (?, ?, ?, ?, ?)",
        ("job-1", "completed", 5, "job_titles_es", 1234567890),
    )
    conn.execute(
        "INSERT INTO clusters (job_id, representative_original, normalized_key, member_count, male_es, female_es, category) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("job-1", "jefe compras", "jefe compras", 2, "Jefe de Compras", "Jefa de Compras", "Supply Chain"),
    )
    cluster_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO job_rows (job_id, row_index, original, normalized, cluster_id) VALUES (?, ?, ?, ?, ?)",
        ("job-1", 0, "row1", "row1", cluster_id),
    )
    conn.execute(
        "INSERT INTO job_rows (job_id, row_index, original, normalized, cluster_id) VALUES (?, ?, ?, ?, ?)",
        ("job-1", 1, "row2", "row2", cluster_id),
    )
    conn.commit()

    with caplog.at_level("ERROR"):
        with pytest.raises(RowCountDriftError):
            export_job_to_csv(conn, "job-1")

    # Check that the error was logged
    assert len(caplog.records) > 0
    log_record = caplog.records[0]
    assert log_record.name == "nomenclator.export"
    assert log_record.message == "export.row_count_drift"
    assert log_record.job_id == "job-1"
    assert log_record.in_count == 5
    assert log_record.out_count == 2
