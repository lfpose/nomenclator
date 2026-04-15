import pytest
from backend.app.csv_io.exporter import download_filename


def test_download_filename_strips_hyphens():
    """Verifies hyphens are stripped from job ID."""
    job_id = "a1b2-c3d4-e5f6-g7h8"
    filename = download_filename(job_id)
    assert "a1b2c3d4" in filename  # Hyphens stripped
    assert "-" not in filename.replace("nomenclator-", "")


def test_download_filename_starts_with_prefix():
    """Verifies filename starts with 'nomenclator-' prefix."""
    job_id = "a1b2-c3d4-e5f6-g7h8"
    filename = download_filename(job_id)
    assert filename.startswith("nomenclator-")


def test_download_filename_uses_8_chars():
    """Verifies filename uses exactly 8 characters from job ID."""
    job_id = "a1b2-c3d4-e5f6-g7h8"
    filename = download_filename(job_id)
    # Extract the part between prefix and .csv
    short_part = filename.replace("nomenclator-", "").replace(".csv", "")
    assert len(short_part) == 8
    # Should be first 8 chars of the stripped job ID
    assert short_part == "a1b2c3d4"


def test_download_filename_short_job_id():
    """Verifies short job IDs are handled correctly."""
    job_id = "abc123"
    filename = download_filename(job_id)
    # Should use all available characters (6 in this case)
    assert filename == "nomenclator-abc123.csv"
    assert filename.endswith(".csv")


def test_download_filename_no_hyphens():
    """Verifies job IDs without hyphens are handled correctly."""
    job_id = "a1b2c3d4e5f6g7h8"
    filename = download_filename(job_id)
    # Should take first 8 characters
    assert filename == "nomenclator-a1b2c3d4.csv"
