import logging

import pytest

from app.dao import jobs as jobs_dao
from app.jobs.service import transition


def test_transition_draft_to_preview_updates_db(conn):
    """Verifies transition updates job status in database."""
    job_id = jobs_dao.create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    transition(conn, job_id, "preview", reason="user_preview")
    updated = jobs_dao.get_job(conn, job_id)
    assert updated is not None
    assert updated.status == "preview"


def test_transition_raises_on_invalid_from_state(conn):
    """Verifies invalid transition raises ValueError."""
    job_id = jobs_dao.create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    # draft -> completed is not an allowed transition
    with pytest.raises(ValueError, match="Invalid transition"):
        transition(conn, job_id, "completed", reason="should_fail")


def test_transition_raises_on_missing_job(conn):
    """Verifies transition raises ValueError for non-existent job."""
    with pytest.raises(ValueError, match="job not found"):
        transition(conn, "nonexistent-job", "preview", reason="should_fail")


def test_transition_logs_structured_event(conn, caplog):
    """Verifies transition logs structured event with job_id, from, to, reason."""
    job_id = jobs_dao.create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    with caplog.at_level(logging.INFO):
        transition(conn, job_id, "preview", reason="test_reason")
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.message == "job.transition"
    assert record.job_id == job_id
    assert getattr(record, "from") == "draft"
    assert record.to == "preview"
    assert record.reason == "test_reason"
