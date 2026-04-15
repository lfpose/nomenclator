"""Tests for spend cap checking."""

import time

from app.dao.jobs import create_job
from app.dao.spend_log import insert_spend
from app.jobs.estimator import CapCheckResult, check_cap
from app.pricing import MONTHLY_SPEND_CAP_USD


def test_cap_ok_when_empty_spend_log(conn):
    """When no spend entries exist, cap check should succeed for estimates under cap."""
    result = check_cap(conn, estimated_usd=10.0)
    assert isinstance(result, CapCheckResult)
    assert result.ok is True
    assert result.used_usd == 0.0
    assert result.estimated_usd == 10.0
    assert result.cap_usd == MONTHLY_SPEND_CAP_USD
    assert result.reset_date_unix is None


def test_cap_blocked_when_used_plus_est_over_20(conn):
    """When used + estimated exceeds cap, cap check should fail."""
    now = int(time.time())
    # Create a job first for FK constraint
    job1_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    # Record $19.90 of spend (no batch, just a job-level spend entry)
    insert_spend(conn, job_id=job1_id, batch_id=None, usd=19.90, at=now - 1000)

    result = check_cap(conn, estimated_usd=0.20, now=now)
    assert result.ok is False
    assert result.used_usd == 19.90
    assert result.estimated_usd == 0.20
    assert result.cap_usd == MONTHLY_SPEND_CAP_USD
    # 19.90 + 0.20 = 20.10 > 20.00


def test_cap_ok_when_used_plus_est_exactly_20(conn):
    """When used + estimated equals cap exactly, cap check should succeed."""
    now = int(time.time())
    # Create a job first for FK constraint
    job1_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    # Record $19.00 of spend
    insert_spend(conn, job_id=job1_id, batch_id=None, usd=19.00, at=now - 1000)

    result = check_cap(conn, estimated_usd=1.00, now=now)
    assert result.ok is True
    assert result.used_usd == 19.00
    assert result.estimated_usd == 1.00
    assert result.cap_usd == MONTHLY_SPEND_CAP_USD
    # 19.00 + 1.00 = 20.00 exactly


def test_cap_ignores_old_entries(conn):
    """Spend entries older than 30 days should be ignored."""
    now = int(time.time())
    thirty_one_days = 31 * 24 * 60 * 60
    # Create jobs first for FK constraint
    job1_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    job2_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    # Record $15.00 of spend 31 days ago (outside window)
    insert_spend(conn, job_id=job1_id, batch_id=None, usd=15.00, at=now - thirty_one_days)
    # Record $5.00 of spend recently (inside window)
    insert_spend(conn, job_id=job2_id, batch_id=None, usd=5.00, at=now - 1000)

    result = check_cap(conn, estimated_usd=10.00, now=now)
    # Only $5.00 from recent entry should count, 5 + 10 = 15 < 20
    assert result.ok is True
    assert result.used_usd == 5.00
    assert result.estimated_usd == 10.00


def test_cap_returns_reset_date_when_entries_exist(conn):
    """When spend entries exist, reset_date should be returned."""
    now = int(time.time())
    # Create a job first for FK constraint
    job1_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    # Record $10.00 of spend
    insert_spend(conn, job_id=job1_id, batch_id=None, usd=10.00, at=now - 1000)

    result = check_cap(conn, estimated_usd=1.00, now=now)
    assert result.reset_date_unix is not None
    # Reset date should be approximately 30 days after the oldest entry
    expected_reset = now - 1000 + (30 * 24 * 60 * 60)
    assert abs(result.reset_date_unix - expected_reset) < 2  # Allow 2 second tolerance


def test_cap_check_skipped_for_dry_run(conn):
    """When is_dry_run=True, cap check should return ok=True with $0 figures."""
    now = int(time.time())
    # Create a job first for FK constraint
    job1_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    # Record $19.90 of spend
    insert_spend(conn, job_id=job1_id, batch_id=None, usd=19.90, at=now - 1000)

    # Even with high spend and estimate, dry_run should return ok=True
    result = check_cap(conn, estimated_usd=10.00, now=now, is_dry_run=True)
    assert result.ok is True
    assert result.used_usd == 0.0
    assert result.estimated_usd == 0.0
    assert result.cap_usd == MONTHLY_SPEND_CAP_USD
    assert result.reset_date_unix is None
