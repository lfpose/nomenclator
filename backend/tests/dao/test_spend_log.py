import time
import pytest

from app.dao.spend_log import SpendLog, insert_spend, sum_last_30_days, reset_date_approx
from app.dao.jobs import create_job
import uuid


def test_insert_spend_persists(conn):
    """Test that insert_spend persists values."""
    job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )

    insert_spend(
        conn,
        job_id=job_id,
        batch_id=None,
        usd=1.23,
        at=1234567890,
    )

    row = conn.execute("SELECT * FROM spend_log WHERE job_id = ?", (job_id,)).fetchone()
    assert row is not None
    assert row["job_id"] == job_id
    assert row["batch_id"] is None
    assert row["usd"] == 1.23
    assert row["at"] == 1234567890


def test_sum_last_30_days_excludes_old_entries(conn):
    """Test that sum_last_30_days excludes entries older than 30 days."""
    job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )

    now = 1234567890

    # Insert entries at different times
    insert_spend(
        conn,
        job_id=job_id,
        batch_id=None,
        usd=5.0,
        at=now - 10 * 86400,  # 10 days ago
    )
    insert_spend(
        conn,
        job_id=job_id,
        batch_id=None,
        usd=3.0,
        at=now - 25 * 86400,  # 25 days ago
    )
    insert_spend(
        conn,
        job_id=job_id,
        batch_id=None,
        usd=2.0,
        at=now - 35 * 86400,  # 35 days ago (outside window)
    )

    total = sum_last_30_days(conn, now=now)
    assert total == 8.0  # 5.0 + 3.0, excluding the 35-day-old entry


def test_sum_last_30_days_returns_zero_when_empty(conn):
    """Test that sum_last_30_days returns 0.0 when there are no entries."""
    total = sum_last_30_days(conn, now=1234567890)
    assert total == 0.0


def test_reset_date_approx_returns_oldest_plus_30(conn):
    """Test that reset_date_approx returns oldest entry + 30 days."""
    job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )

    now = 1234567890

    # Insert entries at different times
    insert_spend(
        conn,
        job_id=job_id,
        batch_id=None,
        usd=5.0,
        at=now - 10 * 86400,  # 10 days ago
    )
    insert_spend(
        conn,
        job_id=job_id,
        batch_id=None,
        usd=3.0,
        at=now - 25 * 86400,  # 25 days ago (oldest)
    )
    insert_spend(
        conn,
        job_id=job_id,
        batch_id=None,
        usd=2.0,
        at=now - 35 * 86400,  # 35 days ago (outside window)
    )

    # The oldest in-window entry is at now - 25 * 86400
    # Reset should be that + 30 days = now + 5 * 86400
    reset_date = reset_date_approx(conn, now=now)
    assert reset_date == (now - 25 * 86400) + (30 * 86400)
    assert reset_date == now + 5 * 86400
