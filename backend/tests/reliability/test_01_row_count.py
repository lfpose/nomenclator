import pytest

from app.csv_io.exporter import export_job_to_csv


@pytest.mark.parametrize("n_rows", [1, 100, 1000, 10000])
def test_row_count_equals_input(n_rows, conn, fake_anthropic, run_e2e):
    """Test that input CSV row count matches output CSV row count.

    For fixtures of 1, 100, 1000, and 10000 rows, a successful run produces
    an output CSV with exactly that many data rows (excluding header).
    """
    job_id = run_e2e(n_rows=n_rows, conn=conn, fake=fake_anthropic)
    csv_bytes = export_job_to_csv(conn, job_id)
    data_rows = csv_bytes.decode("utf-8-sig").splitlines()[1:]  # skip header
    assert len(data_rows) == n_rows
