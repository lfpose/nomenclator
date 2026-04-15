import logging

from app.dao import jobs as jobs_dao
from app.jobs.state_machine import assert_allowed

log = logging.getLogger("nomenclator.jobs")


class ConcurrencyError(Exception):
    """Raised when a job cannot start because another job is already running."""
    pass


def transition(conn, job_id: str, new_status: str, reason: str) -> None:
    """Transition a job to a new status with validation and logging."""
    job = jobs_dao.get_job(conn, job_id)
    if job is None:
        raise ValueError(f"job not found: {job_id}")
    assert_allowed(job.status, new_status)
    jobs_dao.update_job_status(conn, job_id, new_status)
    log.info(
        "job.transition",
        extra={"job_id": job_id, "from": job.status, "to": new_status, "reason": reason},
    )


def assert_no_running_job(conn) -> None:
    """Raise ConcurrencyError if any non-terminal job exists."""
    if jobs_dao.count_active_jobs(conn) > 0:
        raise ConcurrencyError("job_already_running")
