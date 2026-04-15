import pytest

from app.dao.jobs import (
    create_job,
    get_job,
    list_jobs,
    update_job_status,
    update_job_counts,
    count_active_jobs,
)
import uuid


def test_create_job_returns_valid_uuid(conn):
    """Test that create_job returns a valid UUID."""
    job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    assert len(job_id) == 36
    # Verify it's a valid UUID
    uuid.UUID(job_id)


def test_get_job_after_create_roundtrips(conn):
    """Test that get_job returns the job that was created."""
    job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=85,
        titles_per_request=30,
    )
    
    job = get_job(conn, job_id)
    assert job is not None
    assert job.id == job_id
    assert job.task_template_id == "job_titles_es"
    assert job.status == "draft"
    assert job.fuzzy_threshold == 85
    assert job.titles_per_request == 30


def test_list_jobs_ordered_newest_first(conn):
    """Test that list_jobs returns jobs ordered by created_at DESC."""
    # Create jobs with explicit timestamps to ensure ordering
    job_id1 = create_job(conn, task_template_id="job_titles_es", fuzzy_threshold=90, titles_per_request=25)
    conn.execute("UPDATE jobs SET created_at = 1000 WHERE id = ?", (job_id1,))
    
    job_id2 = create_job(conn, task_template_id="job_titles_es", fuzzy_threshold=90, titles_per_request=25)
    conn.execute("UPDATE jobs SET created_at = 2000 WHERE id = ?", (job_id2,))
    
    job_id3 = create_job(conn, task_template_id="job_titles_es", fuzzy_threshold=90, titles_per_request=25)
    conn.execute("UPDATE jobs SET created_at = 3000 WHERE id = ?", (job_id3,))
    
    jobs = list_jobs(conn)
    assert len(jobs) == 3
    # Verify ordering by created_at DESC
    assert jobs[0].id == job_id3  # newest (highest created_at)
    assert jobs[1].id == job_id2
    assert jobs[2].id == job_id1  # oldest (lowest created_at)


def test_update_job_status_persists(conn):
    """Test that update_job_status persists the new status."""
    job_id = create_job(conn, task_template_id="job_titles_es", fuzzy_threshold=90, titles_per_request=25)
    
    update_job_status(conn, job_id, "preview")
    job = get_job(conn, job_id)
    assert job.status == "preview"
    
    update_job_status(conn, job_id, "queued")
    job = get_job(conn, job_id)
    assert job.status == "queued"


def test_update_job_counts_persists_all_fields(conn):
    """Test that update_job_counts persists all provided count fields."""
    job_id = create_job(conn, task_template_id="job_titles_es", fuzzy_threshold=90, titles_per_request=25)
    
    update_job_counts(
        conn,
        job_id,
        total_rows=100,
        exact_unique_rows=80,
        cluster_count=20,
        completed_rows=15,
        error_rows=2,
        est_cost_usd=0.50,
        actual_cost_usd=0.45,
        finished_at=1234567890,
    )
    
    job = get_job(conn, job_id)
    assert job.total_rows == 100
    assert job.exact_unique_rows == 80
    assert job.cluster_count == 20
    assert job.completed_rows == 15
    assert job.error_rows == 2
    assert job.est_cost_usd == 0.50
    assert job.actual_cost_usd == 0.45
    assert job.finished_at == 1234567890


def test_count_active_jobs_ignores_terminal_states(conn):
    """Test that count_active_jobs only counts non-terminal jobs."""
    # Create jobs in various states
    job1 = create_job(conn, task_template_id="job_titles_es", fuzzy_threshold=90, titles_per_request=25)
    update_job_status(conn, job1, "queued")
    
    job2 = create_job(conn, task_template_id="job_titles_es", fuzzy_threshold=90, titles_per_request=25)
    update_job_status(conn, job2, "submitted")
    
    job3 = create_job(conn, task_template_id="job_titles_es", fuzzy_threshold=90, titles_per_request=25)
    update_job_status(conn, job3, "polling")
    
    job4 = create_job(conn, task_template_id="job_titles_es", fuzzy_threshold=90, titles_per_request=25)
    update_job_status(conn, job4, "retrying")
    
    job5 = create_job(conn, task_template_id="job_titles_es", fuzzy_threshold=90, titles_per_request=25)
    update_job_status(conn, job5, "completed")
    
    job6 = create_job(conn, task_template_id="job_titles_es", fuzzy_threshold=90, titles_per_request=25)
    update_job_status(conn, job6, "failed")
    
    job7 = create_job(conn, task_template_id="job_titles_es", fuzzy_threshold=90, titles_per_request=25)
    update_job_status(conn, job7, "cancelled")
    
    # Only non-terminal states should be counted
    active_count = count_active_jobs(conn)
    assert active_count == 4  # queued, submitted, polling, retrying


def test_get_nonexistent_job_returns_none(conn):
    """Test that get_job returns None for a nonexistent job ID."""
    job = get_job(conn, "nonexistent-job-id")
    assert job is None


def test_create_job_with_row_subset_params(conn):
    """Test that create_job preserves row_subset_mode and row_subset_n."""
    job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
        row_subset_mode="first_n",
        row_subset_n=500,
    )
    
    job = get_job(conn, job_id)
    assert job.row_subset_mode == "first_n"
    assert job.row_subset_n == 500


def test_create_job_with_dry_run_flag(conn):
    """Test that create_job preserves the is_dry_run flag."""
    job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
        is_dry_run=True,
    )
    
    job = get_job(conn, job_id)
    assert job.is_dry_run is True
    
    # Test that default is False
    job_id2 = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )
    
    job2 = get_job(conn, job_id2)
    assert job2.is_dry_run is False
