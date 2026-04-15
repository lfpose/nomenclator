"""Tests for create_preview_job with row subset functionality."""
from app.jobs.service import create_preview_job


def test_preview_all_mode_processes_all_rows(conn):
    """Test that 'all' mode processes all input rows."""
    text = "Jefe de Compras\nGerente Ventas\nDirector IT\nAnalista RRHH\nCoordinador Marketing"
    result = create_preview_job(
        conn,
        text=text,
        threshold=90,
        titles_per_request=25,
        row_subset_mode="all",
    )
    assert result.total_input_rows == 5
    assert result.selected_rows == 5
    assert result.total_rows == 5


def test_preview_first_n_processes_only_n_rows(conn):
    """Test that 'first_n' mode processes only the first N rows."""
    # Create 10 rows
    rows = [f"Title {i}" for i in range(10)]
    text = "\n".join(rows)
    result = create_preview_job(
        conn,
        text=text,
        threshold=90,
        titles_per_request=25,
        row_subset_mode="first_n",
        row_subset_n=3,
    )
    assert result.total_input_rows == 10
    assert result.selected_rows == 3
    assert result.total_rows == 3


def test_preview_random_n_processes_only_n_rows(conn):
    """Test that 'random_n' mode processes exactly N rows."""
    # Create 20 rows
    rows = [f"Title {i}" for i in range(20)]
    text = "\n".join(rows)
    result = create_preview_job(
        conn,
        text=text,
        threshold=90,
        titles_per_request=25,
        row_subset_mode="random_n",
        row_subset_n=5,
    )
    assert result.total_input_rows == 20
    assert result.selected_rows == 5
    assert result.total_rows == 5


def test_preview_subset_larger_than_input_uses_all(conn):
    """Test that subset N larger than input count uses all rows."""
    text = "Title A\nTitle B\nTitle C"
    result = create_preview_job(
        conn,
        text=text,
        threshold=90,
        titles_per_request=25,
        row_subset_mode="first_n",
        row_subset_n=10,  # More than input count
    )
    assert result.total_input_rows == 3
    assert result.selected_rows == 3
    assert result.total_rows == 3


def test_preview_stores_row_subset_mode_on_job(conn):
    """Test that row subset mode is stored on the job."""
    text = "Jefe de Compras\nGerente Ventas"
    result = create_preview_job(
        conn,
        text=text,
        threshold=90,
        titles_per_request=25,
        row_subset_mode="random_n",
        row_subset_n=1,
    )

    from app.dao.jobs import get_job
    job = get_job(conn, result.job_id)
    assert job is not None
    assert job.row_subset_mode == "random_n"
    assert job.row_subset_n == 1


def test_preview_result_includes_total_and_selected_counts(conn):
    """Test that PreviewResult includes total_input_rows and selected_rows."""
    # Create 15 rows, select 7
    rows = [f"Title {i}" for i in range(15)]
    text = "\n".join(rows)
    result = create_preview_job(
        conn,
        text=text,
        threshold=90,
        titles_per_request=25,
        row_subset_mode="first_n",
        row_subset_n=7,
    )

    assert hasattr(result, "total_input_rows")
    assert hasattr(result, "selected_rows")
    assert result.total_input_rows == 15
    assert result.selected_rows == 7
    assert result.total_rows == 7  # total_rows equals selected_rows
