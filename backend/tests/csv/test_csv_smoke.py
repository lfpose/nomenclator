"""CSV integration smoke test."""
import gzip
import time

import pytest

from app.csv_io.dedup import unique_normalized
from app.csv_io.ingest import ingest


def test_smoke_ingests_13k_under_2s():
    """Test that ingesting 13k rows completes in under 2 seconds."""
    with gzip.open("tests/fixtures/csv/realistic_13k.csv.gz", "rb") as f:
        raw_bytes = f.read()

    start = time.perf_counter()
    rows = ingest(file_bytes=raw_bytes)
    elapsed = time.perf_counter() - start

    assert len(rows) == 13000, f"Expected 13000 rows, got {len(rows)}"
    assert elapsed < 2.0, f"Ingestion took {elapsed:.2f}s, expected < 2s"


def test_smoke_dedup_reduces_by_at_least_30_percent():
    """Test that deduplication reduces row count by at least 30%."""
    with gzip.open("tests/fixtures/csv/realistic_13k.csv.gz", "rb") as f:
        raw_bytes = f.read()

    rows = ingest(file_bytes=raw_bytes)
    unique = unique_normalized(rows)

    reduction_pct = (len(rows) - len(unique)) / len(rows) * 100
    assert reduction_pct >= 30.0, (
        f"Expected at least 30% reduction, got {reduction_pct:.1f}% "
        f"({len(rows)} -> {len(unique)})"
    )


def test_smoke_all_originals_preserved():
    """Test that all original row values are preserved in the input."""
    with gzip.open("tests/fixtures/csv/realistic_13k.csv.gz", "rb") as f:
        raw_bytes = f.read()

    rows = ingest(file_bytes=raw_bytes)

    # Check that row indices are 0..12999
    indices = [row[0] for row in rows]
    assert indices == list(range(13000)), "Row indices should be 0..12999"

    # Check that original values are strings (not None or empty)
    originals = [row[1] for row in rows]
    assert all(isinstance(orig, str) for orig in originals), "All originals should be strings"
    assert all(orig for orig in originals), "No original should be empty"

    # Check that all normalized values are non-empty
    normalized = [row[2] for row in rows]
    assert all(norm for norm in normalized), "No normalized value should be empty"
