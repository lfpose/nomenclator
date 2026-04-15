"""End-to-end tests for happy path using FakeAnthropicBatchClient."""

import os
import sqlite3
import tempfile
import pytest

from app.db import _apply_migrations
from app.dao import clusters as clusters_dao
from app.dao import jobs as jobs_dao
from app.dao import spend_log as spend_log_dao
from app.jobs.service import commit_job, create_preview_job
from app.worker.poller import Worker


@pytest.fixture
def temp_db():
    """Create a temporary file-based database for testing.

    File-based DB allows multiple connections to the same database,
    which is needed because worker.tick() closes connections.
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Create and initialize DB
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    _apply_migrations(conn)
    conn.close()

    yield path

    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


def get_temp_db_factory(path):
    """Factory function that returns a fresh connection to temp database."""
    def factory():
        conn = sqlite3.connect(path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn
    return factory


def test_e2e_happy_path_completes(temp_db, fake_anthropic):
    """Verify that a job completes successfully through the full worker flow.

    This test walks through:
    1. Create preview job with 20 titles (clusters to ~5)
    2. Commit job to Anthropic (fake)
    3. Complete batch with valid results
    4. Worker tick processes results
    5. Job transitions to completed
    """
    # Create input with 20 job titles that will cluster to ~5 groups
    titles = """Jefe de Compras
Jefe Compras
Jefe de compras
Ingeniero de Software
Ingeniero Software
Gerente de Producto
Gerente Producto
VP de Ventas
Vicepresidente de Ventas
Director de Finanzas
Director Finanzas
Contador General
Contador
Analista de Marketing
Analista Marketing
Diseñador Gráfico
Diseñador Gráfica
Representante de Ventas
Repr de Ventas
Coord. de Recursos Humanos"""

    # Create connection and job
    conn = sqlite3.connect(temp_db, isolation_level=None)
    conn.row_factory = sqlite3.Row

    # Create preview job
    preview = create_preview_job(
        conn,
        text=titles,
        threshold=90,
        titles_per_request=25,
    )

    # Commit the job
    commit_job(conn, fake_anthropic, preview.job_id, taxonomy=None, prompt_override=None)

    # Verify job is in submitted state
    job = jobs_dao.get_job(conn, preview.job_id)
    assert job.status == "submitted"

    # Get the batch ID and request IDs
    from app.dao import batches as batches_dao
    from app.dao import batch_requests as batch_requests_dao
    batches = batches_dao.list_batches_for_job(conn, preview.job_id)
    assert len(batches) == 1
    batch_id = batches[0].id

    # Get the actual request IDs that were created by commit_job
    requests = batch_requests_dao.list_requests_for_batch(conn, batch_id)
    assert len(requests) > 0

    # Get cluster information for building results
    clusters = clusters_dao.list_clusters(conn, preview.job_id)
    assert len(clusters) > 0

    # Build valid Anthropic results for each request
    results = []
    for req_idx, req in enumerate(requests):
        cluster_ids = req.cluster_ids
        # Build results for each cluster in this request
        cluster_results = []
        for cluster_idx, cluster_id in enumerate(cluster_ids):
            # Find the cluster in the list
            cluster = next((c for c in clusters if c.id == cluster_id), None)
            assert cluster is not None, f"Cluster {cluster_id} not found"
            cluster_results.append({
                "id": f"t{(cluster_idx + 1):03d}",
                "male_es": cluster.representative_original,
                "female_es": cluster.representative_original.replace("o", "a") if "o" in cluster.representative_original else cluster.representative_original + "a",
                "category": "Professional",
            })

        # Create a result for this request with the correct custom_id
        results.append({
            "custom_id": req.id,  # Use the actual request ID from batch_requests
            "result": {
                "message": {
                    "usage": {"input_tokens": 1000, "output_tokens": 500},
                    "content": [{
                        "type": "tool_use",
                        "name": "emit_standardized_titles",
                        "input": {
                            "results": cluster_results
                        }
                    }],
                    "stop_reason": "end_turn",
                }
            }
        })

    # Close connection before worker tick
    conn.close()

    # Complete the batch with valid results
    fake_anthropic.complete_batch(batch_id, results)

    # Create worker and tick to process the batch
    db_factory = get_temp_db_factory(temp_db)
    worker = Worker(client=fake_anthropic, db_factory=db_factory)
    import asyncio
    asyncio.run(worker.tick())

    # Verify job completed with new connection
    conn2 = sqlite3.connect(temp_db, isolation_level=None)
    conn2.row_factory = sqlite3.Row
    job = jobs_dao.get_job(conn2, preview.job_id)
    conn2.close()
    assert job.status == "completed"


def test_e2e_happy_path_all_clusters_populated(temp_db, fake_anthropic):
    """Verify that all clusters get populated with answers after the happy path.

    This is a more detailed check that cluster answers are written correctly.
    """
    # Create input with titles that will cluster
    titles = """Jefe de Compras
Jefe Compras
Jefe de compras
Ingeniero de Software
Ingeniero Software
Gerente de Producto
Gerente Producto
VP de Ventas
Vicepresidente de Ventas
Director de Finanzas"""

    # Create connection and job
    conn = sqlite3.connect(temp_db, isolation_level=None)
    conn.row_factory = sqlite3.Row

    # Create preview job
    preview = create_preview_job(
        conn,
        text=titles,
        threshold=90,
        titles_per_request=25,
    )

    # Commit the job
    commit_job(conn, fake_anthropic, preview.job_id, taxonomy=None, prompt_override=None)

    # Get the batch ID and request IDs
    from app.dao import batches as batches_dao
    from app.dao import batch_requests as batch_requests_dao
    batches = batches_dao.list_batches_for_job(conn, preview.job_id)
    batch_id = batches[0].id

    requests = batch_requests_dao.list_requests_for_batch(conn, batch_id)

    clusters = clusters_dao.list_clusters(conn, preview.job_id)

    # Build valid Anthropic results for each request
    results = []
    for req in requests:
        cluster_ids = req.cluster_ids
        cluster_results = []
        for cluster_idx, cluster_id in enumerate(cluster_ids):
            cluster = next((c for c in clusters if c.id == cluster_id), None)
            assert cluster is not None
            cluster_results.append({
                "id": f"t{(cluster_idx + 1):03d}",
                "male_es": cluster.representative_original,
                "female_es": cluster.representative_original.replace("o", "a") if "o" in cluster.representative_original else cluster.representative_original + "a",
                "category": "Professional",
            })

        results.append({
            "custom_id": req.id,
            "result": {
                "message": {
                    "usage": {"input_tokens": 1000, "output_tokens": 500},
                    "content": [{
                        "type": "tool_use",
                        "name": "emit_standardized_titles",
                        "input": {
                            "results": cluster_results
                        }
                    }],
                    "stop_reason": "end_turn",
                }
            }
        })

    # Close connection before worker tick
    conn.close()

    # Complete the batch and tick
    fake_anthropic.complete_batch(batch_id, results)
    db_factory = get_temp_db_factory(temp_db)
    worker = Worker(client=fake_anthropic, db_factory=db_factory)
    import asyncio
    asyncio.run(worker.tick())

    # Verify all clusters have answers with new connection
    conn2 = sqlite3.connect(temp_db, isolation_level=None)
    conn2.row_factory = sqlite3.Row
    clusters_after = clusters_dao.list_clusters(conn2, preview.job_id)
    conn2.close()
    for cluster in clusters_after:
        assert cluster.male_es is not None
        assert cluster.female_es is not None
        assert cluster.category is not None
        assert cluster.error is None


def test_e2e_happy_path_spend_log_entry_recorded(temp_db, fake_anthropic):
    """Verify that spend is logged correctly after the happy path completes.

    The worker should record input/output token counts as USD spend.
    """
    # Create input
    titles = """Jefe de Compras
Jefe Compras
Ingeniero de Software
Gerente de Producto"""

    # Create connection and job
    conn = sqlite3.connect(temp_db, isolation_level=None)
    conn.row_factory = sqlite3.Row

    # Create preview job
    preview = create_preview_job(
        conn,
        text=titles,
        threshold=90,
        titles_per_request=25,
    )

    # Commit the job
    commit_job(conn, fake_anthropic, preview.job_id, taxonomy=None, prompt_override=None)

    # Get batch and request info
    from app.dao import batches as batches_dao
    from app.dao import batch_requests as batch_requests_dao
    batches = batches_dao.list_batches_for_job(conn, preview.job_id)
    batch_id = batches[0].id

    requests = batch_requests_dao.list_requests_for_batch(conn, batch_id)

    clusters = clusters_dao.list_clusters(conn, preview.job_id)

    # Build results with known token counts
    input_tokens = 2000
    output_tokens = 1000
    results = []
    for req in requests:
        cluster_ids = req.cluster_ids
        cluster_results = []
        for cluster_idx, cluster_id in enumerate(cluster_ids):
            cluster = next((c for c in clusters if c.id == cluster_id), None)
            assert cluster is not None
            cluster_results.append({
                "id": f"t{(cluster_idx + 1):03d}",
                "male_es": cluster.representative_original,
                "female_es": cluster.representative_original.replace("o", "a") if "o" in cluster.representative_original else cluster.representative_original + "a",
                "category": "Professional",
            })

        results.append({
            "custom_id": req.id,
            "result": {
                "message": {
                    "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
                    "content": [{
                        "type": "tool_use",
                        "name": "emit_standardized_titles",
                        "input": {
                            "results": cluster_results
                        }
                    }],
                    "stop_reason": "end_turn",
                }
            }
        })

    # Close connection before worker tick
    conn.close()

    # Complete the batch and tick
    fake_anthropic.complete_batch(batch_id, results)
    db_factory = get_temp_db_factory(temp_db)
    worker = Worker(client=fake_anthropic, db_factory=db_factory)
    import asyncio
    asyncio.run(worker.tick())

    # Verify spend was logged with new connection
    conn2 = sqlite3.connect(temp_db, isolation_level=None)
    conn2.row_factory = sqlite3.Row
    total_spend = spend_log_dao.sum_last_30_days(conn2)
    # Calculate expected USD: (input_tokens / 1M) * $0.4 + (output_tokens / 1M) * $2.0
    # For each request with input_tokens + output_tokens
    total_input = input_tokens * len(requests)
    total_output = output_tokens * len(requests)
    expected_usd = (total_input / 1_000_000) * 0.4 + (total_output / 1_000_000) * 2.0
    assert abs(total_spend - expected_usd) < 0.001  # Allow small floating point error

    # Verify spend entries have correct job_id
    spend_entries = conn2.execute(
        "SELECT * FROM spend_log WHERE job_id = ?",
        (preview.job_id,)
    ).fetchall()
    conn2.close()
    assert len(spend_entries) > 0
