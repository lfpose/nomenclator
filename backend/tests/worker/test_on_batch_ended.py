"""Tests for _on_batch_ended functionality in the worker."""

import pytest

from app.worker.poller import Worker
from tests.anthropic.fake_client import FakeAnthropicBatchClient


def test_on_batch_ended_writes_answers_to_clusters(conn, fake_anthropic):
    """Verify that cluster answers are written correctly when batch ends."""
    # Create a job and clusters
    conn.execute(
        """
        INSERT INTO jobs (id, created_at, status, task_template_id, fuzzy_threshold, titles_per_request)
        VALUES ('job1', strftime('%s', 'now'), 'submitted', 'job_titles_es', 90, 2)
        """
    )
    conn.execute(
        """
        INSERT INTO clusters (job_id, representative_original, normalized_key, member_count)
        VALUES
            ('job1', 'Jefe de Compras', 'jefe de compras', 2),
            ('job1', 'Ingeniero de Software', 'ingeniero de software', 1)
        """
    )
    conn.execute(
        """
        INSERT INTO batches (id, job_id, retry_round, parent_batch_id, submitted_at, status, request_count)
        VALUES ('batch1', 'job1', 0, NULL, strftime('%s', 'now'), 'in_progress', 1)
        """
    )
    conn.execute(
        """
        INSERT INTO batch_requests (id, batch_id, cluster_ids, status)
        VALUES ('req1', 'batch1', '[1, 2]', 'pending')
        """
    )

    # Add batch to fake client so complete_batch() can find it
    from tests.anthropic.fake_client import FakeBatch
    fake_anthropic.batches['batch1'] = FakeBatch(id='batch1', requests=[])

    # Complete the batch with valid results
    fake_anthropic.complete_batch(
        'batch1',
        results=[{
            "custom_id": "req1",
            "result": {
                "message": {
                    "usage": {"input_tokens": 1000, "output_tokens": 500},
                    "content": [{
                        "type": "tool_use",
                        "name": "emit_standardized_titles",
                        "input": {
                            "results": [
                                {"id": "t001", "male_es": "Jefe de Compras", "female_es": "Jefa de Compras", "category": "Management"},
                                {"id": "t002", "male_es": "Ingeniero de Software", "female_es": "Ingeniera de Software", "category": "Engineering"},
                            ]
                        }
                    }],
                    "stop_reason": "end_turn",
                }
            }
        }]
    )

    # Create worker and call _on_batch_ended
    worker = Worker(client=fake_anthropic, db_factory=lambda: conn)
    job = conn.execute("SELECT * FROM jobs WHERE id = 'job1'").fetchone()
    batch = conn.execute("SELECT * FROM batches WHERE id = 'batch1'").fetchone()
    from unittest.mock import MagicMock
    import asyncio

    async def run_test():
        # Convert row to dict
        job_dict = dict(job)
        job_obj = MagicMock(**job_dict)
        batch_dict = dict(batch)
        batch_obj = MagicMock(**batch_dict)
        batch_obj.id = 'batch1'

        await worker._on_batch_ended(conn, job_obj, batch_obj)

    asyncio.run(run_test())

    # Verify clusters were updated
    clusters = conn.execute("SELECT * FROM clusters ORDER BY id").fetchall()
    assert len(clusters) == 2
    assert clusters[0]["male_es"] == "Jefe de Compras"
    assert clusters[0]["female_es"] == "Jefa de Compras"
    assert clusters[0]["category"] == "Management"
    assert clusters[1]["male_es"] == "Ingeniero de Software"
    assert clusters[1]["female_es"] == "Ingeniera de Software"
    assert clusters[1]["category"] == "Engineering"


def test_on_batch_ended_records_spend(conn, fake_anthropic):
    """Verify that spend is recorded correctly when batch ends."""
    # Create a job and cluster
    conn.execute(
        """
        INSERT INTO jobs (id, created_at, status, task_template_id, fuzzy_threshold, titles_per_request)
        VALUES ('job1', strftime('%s', 'now'), 'submitted', 'job_titles_es', 90, 1)
        """
    )
    conn.execute(
        """
        INSERT INTO clusters (job_id, representative_original, normalized_key, member_count)
        VALUES ('job1', 'Jefe de Compras', 'jefe de compras', 1)
        """
    )
    conn.execute(
        """
        INSERT INTO batches (id, job_id, retry_round, parent_batch_id, submitted_at, status, request_count)
        VALUES ('batch1', 'job1', 0, NULL, strftime('%s', 'now'), 'in_progress', 1)
        """
    )
    conn.execute(
        """
        INSERT INTO batch_requests (id, batch_id, cluster_ids, status)
        VALUES ('req1', 'batch1', '[1]', 'pending')
        """
    )

    # Add batch to fake client so complete_batch() can find it
    from tests.anthropic.fake_client import FakeBatch
    fake_anthropic.batches['batch1'] = FakeBatch(id='batch1', requests=[])

    # Complete the batch with specific token counts
    fake_anthropic.complete_batch(
        'batch1',
        results=[{
            "custom_id": "req1",
            "result": {
                "message": {
                    "usage": {"input_tokens": 1234, "output_tokens": 5678},
                    "content": [{
                        "type": "tool_use",
                        "name": "emit_standardized_titles",
                        "input": {
                            "results": [{"id": "t001", "male_es": "Jefe de Compras", "female_es": "Jefa de Compras", "category": "Management"}]
                        }
                    }],
                    "stop_reason": "end_turn",
                }
            }
        }]
    )

    # Create worker and call _on_batch_ended
    worker = Worker(client=fake_anthropic, db_factory=lambda: conn)
    job = conn.execute("SELECT * FROM jobs WHERE id = 'job1'").fetchone()
    batch = conn.execute("SELECT * FROM batches WHERE id = 'batch1'").fetchone()
    from unittest.mock import MagicMock
    import asyncio

    async def run_test():
        job_dict = dict(job)
        job_obj = MagicMock(**job_dict)
        batch_dict = dict(batch)
        batch_obj = MagicMock(**batch_dict)
        batch_obj.id = 'batch1'

        await worker._on_batch_ended(conn, job_obj, batch_obj)

    asyncio.run(run_test())

    # Verify spend was recorded
    spend = conn.execute("SELECT * FROM spend_log").fetchall()
    assert len(spend) == 1
    # Access columns by name using dict() conversion
    spend_dict = dict(spend[0])
    assert spend_dict["job_id"] == "job1"
    assert spend_dict["batch_id"] == "batch1"
    # Expected USD: 1234/1e6 * 0.4 + 5678/1e6 * 2.0 = 0.0004936 + 0.011356 = 0.0118496
    assert abs(spend_dict["usd"] - 0.01185) < 0.00001


def test_on_batch_ended_marks_schema_violation_requests_failed(conn, fake_anthropic):
    """Verify that requests with schema violations are marked as failed."""
    # Create a job and cluster
    conn.execute(
        """
        INSERT INTO jobs (id, created_at, status, task_template_id, fuzzy_threshold, titles_per_request)
        VALUES ('job1', strftime('%s', 'now'), 'submitted', 'job_titles_es', 90, 1)
        """
    )
    conn.execute(
        """
        INSERT INTO clusters (job_id, representative_original, normalized_key, member_count)
        VALUES ('job1', 'Jefe de Compras', 'jefe de compras', 1)
        """
    )
    conn.execute(
        """
        INSERT INTO batches (id, job_id, retry_round, parent_batch_id, submitted_at, status, request_count)
        VALUES ('batch1', 'job1', 0, NULL, strftime('%s', 'now'), 'in_progress', 1)
        """
    )
    conn.execute(
        """
        INSERT INTO batch_requests (id, batch_id, cluster_ids, status)
        VALUES ('req1', 'batch1', '[1]', 'pending')
        """
    )

    # Add batch to fake client so complete_batch() can find it
    from tests.anthropic.fake_client import FakeBatch
    fake_anthropic.batches['batch1'] = FakeBatch(id='batch1', requests=[])

    # Complete the batch with schema violation (missing required field)
    fake_anthropic.complete_batch(
        'batch1',
        results=[{
            "custom_id": "req1",
            "result": {
                "message": {
                    "usage": {"input_tokens": 1000, "output_tokens": 500},
                    "content": [{
                        "type": "tool_use",
                        "name": "emit_standardized_titles",
                        "input": {
                            "results": [{"id": "t001", "male_es": "Jefe de Compras", "female_es": "Jefa de Compras"}]  # Missing category
                        }
                    }],
                    "stop_reason": "end_turn",
                }
            }
        }]
    )

    # Create worker and call _on_batch_ended
    worker = Worker(client=fake_anthropic, db_factory=lambda: conn)
    job = conn.execute("SELECT * FROM jobs WHERE id = 'job1'").fetchone()
    batch = conn.execute("SELECT * FROM batches WHERE id = 'batch1'").fetchone()
    from unittest.mock import MagicMock
    import asyncio

    async def run_test():
        job_dict = dict(job)
        job_obj = MagicMock(**job_dict)
        batch_dict = dict(batch)
        batch_obj = MagicMock(**batch_dict)
        batch_obj.id = 'batch1'

        await worker._on_batch_ended(conn, job_obj, batch_obj)

    asyncio.run(run_test())

    # Verify request was marked as failed
    req = conn.execute("SELECT * FROM batch_requests WHERE id = 'req1'").fetchone()
    assert req["status"] == "failed"
    assert req["error"] == "schema_violation"
    assert req["raw_response"] is not None

    # Verify cluster was NOT updated (still NULL)
    cluster = conn.execute("SELECT * FROM clusters WHERE id = 1").fetchone()
    assert cluster["male_es"] is None
    assert cluster["female_es"] is None
    assert cluster["category"] is None


def test_on_batch_ended_marks_request_missing_when_stragglers_present(conn, fake_anthropic):
    """Verify that requests with missing IDs are marked as missing."""
    # Create a job and clusters
    conn.execute(
        """
        INSERT INTO jobs (id, created_at, status, task_template_id, fuzzy_threshold, titles_per_request)
        VALUES ('job1', strftime('%s', 'now'), 'submitted', 'job_titles_es', 90, 2)
        """
    )
    conn.execute(
        """
        INSERT INTO clusters (job_id, representative_original, normalized_key, member_count)
        VALUES
            ('job1', 'Jefe de Compras', 'jefe de compras', 2),
            ('job1', 'Ingeniero de Software', 'ingeniero de software', 1)
        """
    )
    conn.execute(
        """
        INSERT INTO batches (id, job_id, retry_round, parent_batch_id, submitted_at, status, request_count)
        VALUES ('batch1', 'job1', 0, NULL, strftime('%s', 'now'), 'in_progress', 1)
        """
    )
    conn.execute(
        """
        INSERT INTO batch_requests (id, batch_id, cluster_ids, status)
        VALUES ('req1', 'batch1', '[1, 2]', 'pending')
        """
    )

    # Add batch to fake client so complete_batch() can find it
    from tests.anthropic.fake_client import FakeBatch
    fake_anthropic.batches['batch1'] = FakeBatch(id='batch1', requests=[])

    # Complete the batch with only one result (missing t002)
    fake_anthropic.complete_batch(
        'batch1',
        results=[{
            "custom_id": "req1",
            "result": {
                "message": {
                    "usage": {"input_tokens": 1000, "output_tokens": 500},
                    "content": [{
                        "type": "tool_use",
                        "name": "emit_standardized_titles",
                        "input": {
                            "results": [{"id": "t001", "male_es": "Jefe de Compras", "female_es": "Jefa de Compras", "category": "Management"}]
                        }
                    }],
                    "stop_reason": "end_turn",
                }
            }
        }]
    )

    # Create worker and call _on_batch_ended
    worker = Worker(client=fake_anthropic, db_factory=lambda: conn)
    job = conn.execute("SELECT * FROM jobs WHERE id = 'job1'").fetchone()
    batch = conn.execute("SELECT * FROM batches WHERE id = 'batch1'").fetchone()
    from unittest.mock import MagicMock
    import asyncio

    async def run_test():
        job_dict = dict(job)
        job_obj = MagicMock(**job_dict)
        batch_dict = dict(batch)
        batch_obj = MagicMock(**batch_dict)
        batch_obj.id = 'batch1'

        await worker._on_batch_ended(conn, job_obj, batch_obj)

    asyncio.run(run_test())

    # Verify request was marked as missing
    req = conn.execute("SELECT * FROM batch_requests WHERE id = 'req1'").fetchone()
    assert req["status"] == "missing"

    # Verify first cluster was updated
    cluster1 = conn.execute("SELECT * FROM clusters WHERE id = 1").fetchone()
    assert cluster1["male_es"] == "Jefe de Compras"
    assert cluster1["female_es"] == "Jefa de Compras"
    assert cluster1["category"] == "Management"


def test_on_batch_ended_skips_unknown_custom_id(conn, fake_anthropic):
    """Verify that results with unknown custom_id are skipped without error."""
    # Create a job and cluster
    conn.execute(
        """
        INSERT INTO jobs (id, created_at, status, task_template_id, fuzzy_threshold, titles_per_request)
        VALUES ('job1', strftime('%s', 'now'), 'submitted', 'job_titles_es', 90, 1)
        """
    )
    conn.execute(
        """
        INSERT INTO clusters (job_id, representative_original, normalized_key, member_count)
        VALUES ('job1', 'Jefe de Compras', 'jefe de compras', 1)
        """
    )
    conn.execute(
        """
        INSERT INTO batches (id, job_id, retry_round, parent_batch_id, submitted_at, status, request_count)
        VALUES ('batch1', 'job1', 0, NULL, strftime('%s', 'now'), 'in_progress', 1)
        """
    )

    # Add batch to fake client so complete_batch() can find it
    from tests.anthropic.fake_client import FakeBatch
    fake_anthropic.batches['batch1'] = FakeBatch(id='batch1', requests=[])
    # Note: we don't insert a batch request, so the custom_id will be unknown

    # Complete the batch with a result that has no matching request
    fake_anthropic.complete_batch(
        'batch1',
        results=[{
            "custom_id": "unknown_req",
            "result": {
                "message": {
                    "usage": {"input_tokens": 1000, "output_tokens": 500},
                    "content": [{
                        "type": "tool_use",
                        "name": "emit_standardized_titles",
                        "input": {
                            "results": [{"id": "t001", "male_es": "Jefe de Compras", "female_es": "Jefa de Compras", "category": "Management"}]
                        }
                    }],
                    "stop_reason": "end_turn",
                }
            }
        }]
    )

    # Create worker and call _on_batch_ended - should not raise
    worker = Worker(client=fake_anthropic, db_factory=lambda: conn)
    job = conn.execute("SELECT * FROM jobs WHERE id = 'job1'").fetchone()
    batch = conn.execute("SELECT * FROM batches WHERE id = 'batch1'").fetchone()
    from unittest.mock import MagicMock
    import asyncio

    async def run_test():
        job_dict = dict(job)
        job_obj = MagicMock(**job_dict)
        batch_dict = dict(batch)
        batch_obj = MagicMock(**batch_dict)
        batch_obj.id = 'batch1'

        await worker._on_batch_ended(conn, job_obj, batch_obj)

    asyncio.run(run_test())  # Should not raise any exception

    # Verify cluster was NOT updated (since no matching request)
    cluster = conn.execute("SELECT * FROM clusters WHERE id = 1").fetchone()
    assert cluster["male_es"] is None
    assert cluster["female_es"] is None
    assert cluster["category"] is None

    # Verify spend was NOT recorded (no matching request)
    spend = conn.execute("SELECT * FROM spend_log").fetchall()
    assert len(spend) == 0
