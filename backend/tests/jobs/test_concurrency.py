import pytest

from app.dao import jobs as jobs_dao
from app.jobs.service import ConcurrencyError, assert_no_running_job


def test_no_running_job_when_empty(conn):
    """assert_no_running_job should not raise when no active jobs exist."""
    assert_no_running_job(conn)  # Should not raise


def test_raises_when_polling_job_exists(conn):
    """assert_no_running_job should raise ConcurrencyError when a polling job exists."""
    job_id = jobs_dao.create_job(conn, task_template_id="job_titles_es", fuzzy_threshold=90, titles_per_request=25)
    jobs_dao.update_job_status(conn, job_id, "polling")

    with pytest.raises(ConcurrencyError) as exc_info:
        assert_no_running_job(conn)

    assert str(exc_info.value) == "job_already_running"


def test_raises_when_retrying_job_exists(conn):
    """assert_no_running_job should raise ConcurrencyError when a retrying job exists."""
    job_id = jobs_dao.create_job(conn, task_template_id="job_titles_es", fuzzy_threshold=90, titles_per_request=25)
    jobs_dao.update_job_status(conn, job_id, "retrying")

    with pytest.raises(ConcurrencyError) as exc_info:
        assert_no_running_job(conn)

    assert str(exc_info.value) == "job_already_running"


def test_does_not_raise_when_only_completed_jobs(conn):
    """assert_no_running_job should not raise when only completed jobs exist."""
    job_id = jobs_dao.create_job(conn, task_template_id="job_titles_es", fuzzy_threshold=90, titles_per_request=25)
    jobs_dao.update_job_status(conn, job_id, "completed")

    assert_no_running_job(conn)  # Should not raise
