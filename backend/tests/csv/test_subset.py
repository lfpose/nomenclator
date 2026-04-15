import pytest

from app.csv_io.subset import apply_row_subset


@pytest.fixture
def sample_rows():
    """Sample rows for testing: 10 rows with indices 0-9."""
    return [(i, f"title_{i}", f"title_{i}") for i in range(10)]


def test_subset_all_returns_all_rows(sample_rows):
    """Mode 'all' returns all rows regardless of n."""
    result = apply_row_subset(sample_rows, "all", 5, "test-job-123")
    assert result == sample_rows
    assert len(result) == 10


def test_subset_first_n_returns_first_n(sample_rows):
    """Mode 'first_n' returns exactly first n rows."""
    result = apply_row_subset(sample_rows, "first_n", 3, "test-job-123")
    assert len(result) == 3
    assert result[0] == (0, "title_0", "title_0")
    assert result[1] == (1, "title_1", "title_1")
    assert result[2] == (2, "title_2", "title_2")


def test_subset_first_n_preserves_row_index(sample_rows):
    """First_n mode preserves original row_index values."""
    result = apply_row_subset(sample_rows, "first_n", 3, "test-job-123")
    assert result[0][0] == 0
    assert result[1][0] == 1
    assert result[2][0] == 2


def test_subset_random_n_returns_exactly_n(sample_rows):
    """Random_n mode returns exactly n rows."""
    result = apply_row_subset(sample_rows, "random_n", 4, "a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    assert len(result) == 4


def test_subset_random_n_deterministic_with_same_job_id(sample_rows):
    """Same job_id produces same selection across multiple calls."""
    job_id = "deadbeef-feed-cafe-1234-5678abcdef90"
    result1 = apply_row_subset(sample_rows, "random_n", 5, job_id)
    result2 = apply_row_subset(sample_rows, "random_n", 5, job_id)
    assert result1 == result2


def test_subset_random_n_different_job_id_different_selection(sample_rows):
    """Different job_id produces different selection."""
    result1 = apply_row_subset(sample_rows, "random_n", 5, "11111111-1111-1111-1111-111111111111")
    result2 = apply_row_subset(sample_rows, "random_n", 5, "22222222-2222-2222-2222-222222222222")
    assert result1 != result2


def test_subset_n_greater_than_total_returns_all(sample_rows):
    """When n >= total rows, all rows are returned."""
    result = apply_row_subset(sample_rows, "first_n", 15, "test-job-123")
    assert result == sample_rows
    assert len(result) == 10

    result_random = apply_row_subset(sample_rows, "random_n", 15, "test-job-123")
    assert result_random == sample_rows
    assert len(result_random) == 10


def test_subset_preserves_original_row_indices(sample_rows):
    """All subset modes preserve original row_index values."""
    # Test first_n
    result_first = apply_row_subset(sample_rows, "first_n", 5, "test-job")
    original_indices = [r[0] for r in result_first]
    assert original_indices == [0, 1, 2, 3, 4]

    # Test random_n - check that indices are from original set
    result_random = apply_row_subset(sample_rows, "random_n", 3, "12345678-1234-1234-1234-123456789abc")
    random_indices = [r[0] for r in result_random]
    for idx in random_indices:
        assert 0 <= idx < 10
    # Verify sorted (random_n returns sorted indices)
    assert random_indices == sorted(random_indices)
