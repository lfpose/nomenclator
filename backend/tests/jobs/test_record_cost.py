"""Tests for record_batch_cost function in jobs/service.py."""

from app.jobs.service import record_batch_cost


def test_record_batch_cost_inserts_spend_log_entry(conn):
    """Verify that record_batch_cost inserts a spend_log entry."""
    # Create a job first
    from app.dao import jobs as jobs_dao
    job_id = jobs_dao.create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )

    # Record batch cost (no batch_id since we're not creating a real batch)
    usd = record_batch_cost(
        conn,
        job_id=job_id,
        batch_id=None,
        input_tokens=100000,  # 100K input tokens
        output_tokens=50000,  # 50K output tokens
    )

    # Verify spend was recorded
    from app.dao import spend_log as spend_log_dao
    total_spend = spend_log_dao.sum_last_30_days(conn)
    assert total_spend == usd

    # Verify the entry has correct values
    rows = conn.execute(
        "SELECT usd, batch_id FROM spend_log WHERE job_id = ?",
        (job_id,),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["usd"] == usd
    assert rows[0]["batch_id"] is None


def test_record_batch_cost_returns_usd(conn):
    """Verify that record_batch_cost returns the computed USD amount."""
    # Create a job first
    from app.dao import jobs as jobs_dao
    job_id = jobs_dao.create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )

    # Record batch cost with known token counts (no batch_id)
    usd = record_batch_cost(
        conn,
        job_id=job_id,
        batch_id=None,
        input_tokens=100000,  # 100K input tokens
        output_tokens=50000,  # 50K output tokens
    )

    # Expected: (100000 / 1M) * 0.4 + (50000 / 1M) * 2.0 = 0.04 + 0.1 = 0.14
    expected_usd = 0.14
    assert usd == expected_usd
