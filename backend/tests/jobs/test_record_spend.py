"""Tests for record_actual_spend function."""

import pytest

from app.dao.jobs import create_job
from app.dao.spend_log import sum_last_30_days
from app.jobs.estimator import record_actual_spend


def test_record_actual_spend_inserts_row(conn):
    """Test that record_actual_spend inserts a row into spend_log."""
    # Create a job first for FK constraint
    job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )

    # Verify no spend initially
    assert sum_last_30_days(conn) == 0.0

    # Record spend (with batch_id=None to avoid FK constraint on batches table)
    usd = record_actual_spend(
        conn, job_id=job_id, batch_id=None, input_tokens=1000, output_tokens=500
    )

    # Verify spend was inserted
    assert usd > 0.0
    assert sum_last_30_days(conn) == pytest.approx(usd)


def test_record_actual_spend_returns_correct_usd(conn):
    """Test that record_actual_spend returns correct USD calculation."""
    # From pricing.py:
    # HAIKU_BATCH_IN_USD_PER_MTOK = 0.40
    # HAIKU_BATCH_OUT_USD_PER_MTOK = 2.00
    #
    # For 1M input tokens + 1M output tokens:
    # usd = (1M / 1M) * 0.40 + (1M / 1M) * 2.00 = 0.40 + 2.00 = 2.40
    #
    # For 100K input tokens + 50K output tokens:
    # usd = (100K / 1M) * 0.40 + (50K / 1M) * 2.00 = 0.04 + 0.10 = 0.14
    # Create a job first for FK constraint
    job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )

    usd = record_actual_spend(
        conn,
        job_id=job_id,
        batch_id=None,
        input_tokens=100_000,
        output_tokens=50_000,
    )

    expected_usd = 100_000 / 1_000_000 * 0.40 + 50_000 / 1_000_000 * 2.00
    assert usd == pytest.approx(expected_usd)


def test_record_actual_spend_zero_tokens_returns_zero(conn):
    """Test that zero tokens returns zero USD."""
    # Create a job first for FK constraint
    job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )

    usd = record_actual_spend(
        conn,
        job_id=job_id,
        batch_id=None,
        input_tokens=0,
        output_tokens=0,
    )

    assert usd == 0.0

    # Verify no spend was inserted (or zero spend)
    assert sum_last_30_days(conn) == 0.0
