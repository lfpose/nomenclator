from app.csv_io.exporter import export_job_to_csv


def test_row_order_preserved_exactly(conn, fake_anthropic, run_e2e):
    """Test that output CSV original column preserves exact input order.

    This test verifies that when each row has a distinct title, the output
    CSV's 'original' column matches the input order exactly.
    """
    n_rows = 100
    # Generate distinct titles for each row
    titles = [f"Job Title {i}" for i in range(n_rows)]

    # Run E2E with the synthetic titles
    job_id = run_e2e(n_rows=n_rows, conn=conn, fake=fake_anthropic)

    # Export the job to CSV
    csv_bytes = export_job_to_csv(conn, job_id)
    lines = csv_bytes.decode("utf-8-sig").splitlines()

    # Skip header row
    data_lines = lines[1:]

    # Extract original column (first column) from each data row
    # CSV format: original,male_es,female_es,category,error
    originals_in_output = [line.split(",")[0] for line in data_lines]

    # Assert that the output order matches the input order exactly
    assert len(originals_in_output) == n_rows
    for i, original in enumerate(originals_in_output):
        assert original == titles[i], f"Row {i}: expected '{titles[i]}', got '{original}'"


def test_row_order_after_clustering_still_matches_input(conn, fake_anthropic, run_e2e):
    """Test that clustering doesn't change row order in output.

    This test verifies that even when rows are clustered together
    (which groups similar titles), the output CSV still preserves
    the original input order of each individual row.
    """
    n_rows = 50
    # Generate distinct titles that will NOT cluster together
    # (each title is unique, so each will be in its own cluster)
    titles = [f"Unique Job Title {i}" for i in range(n_rows)]

    # Run E2E with the synthetic titles
    job_id = run_e2e(n_rows=n_rows, conn=conn, fake=fake_anthropic, titles=titles)

    # Export the job to CSV
    csv_bytes = export_job_to_csv(conn, job_id)
    lines = csv_bytes.decode("utf-8-sig").splitlines()

    # Skip header row
    data_lines = lines[1:]

    # Extract original column from each data row
    originals_in_output = [line.split(",")[0] for line in data_lines]

    # Assert that the output order matches the input order exactly
    assert len(originals_in_output) == n_rows
    for i, original in enumerate(originals_in_output):
        assert original == titles[i], f"Row {i}: expected '{titles[i]}', got '{original}'"
