"""Integration tests for cap checking with jobs DAO."""

from app.dao.jobs import create_job
from app.dao.spend_log import insert_spend
from app.jobs.estimator import check_cap


def test_cap_multi_spend_scenario_pass_and_fail_boundary(conn):
    """Test cap check passes/fails at the $20 boundary across multiple jobs.

    Scenario:
    - Create 3 jobs with spend $5, $10, $4 (total $19)
    - check_cap(est=$2) should fail (19 + 2 = 21 > 20)
    - check_cap(est=$1) should pass (19 + 1 = 20 exactly)
    """
    # Create 3 jobs
    job_id_1 = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    job_id_2 = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    job_id_3 = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )

    # Record spend: $5, $10, $4 across them (total $19)
    now = 1000000
    insert_spend(conn, job_id=job_id_1, batch_id=None, usd=5.0, at=now)
    insert_spend(conn, job_id=job_id_2, batch_id=None, usd=10.0, at=now)
    insert_spend(conn, job_id=job_id_3, batch_id=None, usd=4.0, at=now)

    # check_cap(est=$2) should fail (19 + 2 = 21 > 20)
    result_2 = check_cap(conn, estimated_usd=2.0, now=now)
    assert not result_2.ok
    assert result_2.used_usd == 19.0
    assert result_2.estimated_usd == 2.0
    assert result_2.cap_usd == 20.0

    # check_cap(est=$1) should pass (19 + 1 = 20 exactly)
    result_1 = check_cap(conn, estimated_usd=1.0, now=now)
    assert result_1.ok
    assert result_1.used_usd == 19.0
    assert result_1.estimated_usd == 1.0
    assert result_1.cap_usd == 20.0


def test_cap_recovers_when_entries_age_out(conn):
    """Test cap check recovers when old entries age out of the 30-day window.

    Scenario:
    - Create jobs with total spend $19
    - Advance time by 31 days for the oldest spend ($5)
    - check_cap(est=$2) should now pass (14 + 2 = 16 <= 20)
    """
    # Create 3 jobs
    job_id_1 = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    job_id_2 = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    job_id_3 = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )

    # Record spend at different times:
    # - $5 at t=0 (oldest)
    # - $10 at t=15 days
    # - $4 at t=25 days
    base_time = 1000000
    insert_spend(conn, job_id=job_id_1, batch_id=None, usd=5.0, at=base_time)
    insert_spend(
        conn,
        job_id=job_id_2,
        batch_id=None,
        usd=10.0,
        at=base_time + (15 * 86400),
    )
    insert_spend(
        conn,
        job_id=job_id_3,
        batch_id=None,
        usd=4.0,
        at=base_time + (25 * 86400),
    )

    # At t=29 days, oldest $5 entry is still in window
    # Total spend = $5 + $10 + $4 = $19
    # check_cap(est=$2) should fail (19 + 2 = 21 > 20)
    time_at_29_days = base_time + (29 * 86400)
    result_at_29 = check_cap(conn, estimated_usd=2.0, now=time_at_29_days)
    assert not result_at_29.ok
    assert result_at_29.used_usd == 19.0

    # Advance time by 31 days from oldest spend
    # Now the $5 entry has aged out
    # Total spend = $10 + $4 = $14
    # check_cap(est=$2) should now pass (14 + 2 = 16 <= 20)
    time_at_31_days = base_time + (31 * 86400)
    result_at_31 = check_cap(conn, estimated_usd=2.0, now=time_at_31_days)
    assert result_at_31.ok
    assert result_at_31.used_usd == 14.0
    assert result_at_31.estimated_usd == 2.0
    assert result_at_31.cap_usd == 20.0
