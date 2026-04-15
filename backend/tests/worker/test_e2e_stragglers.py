"""End-to-end tests for stragglers recovery using FakeAnthropicBatchClient."""

import os
import sqlite3
import tempfile
import pytest

from app.db import _apply_migrations
from app.dao import clusters as clusters_dao
from app.dao import jobs as jobs_dao
from app.dao import batches as batches_dao
from app.dao import batch_requests as batch_requests_dao
from app.jobs.service import commit_job, create_preview_job
from app.worker.poller import Worker
import asyncio


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


def test_e2e_stragglers_recovered_via_retry(temp_db, fake_anthropic):
    """Verify that stragglers (missing results) trigger a retry that recovers them.

    This test walks through:
    1. Create job with 10 clusters, TPR=10 (one request)
    2. Complete initial batch with 9 results (missing cluster 5)
    3. Worker tick detects stragglers, submits retry
    4. Complete retry batch with the 1 missing result
    5. Worker tick completes the job
    6. Assert all 10 clusters populated
    """
    # Create input with 20 job titles that will cluster to ~10 groups
    titles = """Jefe de Compras
Jefe Compras
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
Coord. de Recursos Humanos
Coordinador RH"""

    # Create connection and job
    conn = sqlite3.connect(temp_db, isolation_level=None)
    conn.row_factory = sqlite3.Row

    # Create preview job with TPR=10 to get 10 clusters
    preview = create_preview_job(
        conn,
        text=titles,
        threshold=90,
        titles_per_request=10,  # Each request handles 10 titles
    )

    # Commit the job
    commit_job(conn, fake_anthropic, preview.job_id, taxonomy=None, prompt_override=None)

    # Verify job is in submitted state
    job = jobs_dao.get_job(conn, preview.job_id)
    assert job.status == "submitted"

    # Get the batch ID and request IDs
    batches = batches_dao.list_batches_for_job(conn, preview.job_id)
    assert len(batches) == 1
    batch_id = batches[0].id

    # Get the actual request IDs that were created by commit_job
    requests = batch_requests_dao.list_requests_for_batch(conn, batch_id)
    assert len(requests) > 0

    # Get cluster information for building results
    clusters = clusters_dao.list_clusters(conn, preview.job_id)
    assert len(clusters) > 0

    # Build Anthropic results for the first request with ONE CLUSTER MISSING (cluster 5, index 4)
    results = []
    for req_idx, req in enumerate(requests):
        cluster_ids = req.cluster_ids
        # Build results for each cluster EXCEPT skip index 4 (5th cluster)
        cluster_results = []
        result_indices = []  # Track which cluster indices we include
        for cluster_idx, cluster_id in enumerate(cluster_ids):
            # Skip cluster at index 4 (5th cluster) to create a straggler
            if cluster_idx == 4:
                continue  # This creates the straggler
            result_indices.append(cluster_idx)
            cluster = next((c for c in clusters if c.id == cluster_id), None)
            assert cluster is not None, f"Cluster {cluster_id} not found"
            cluster_results.append({
                "id": f"t{(cluster_idx + 1):03d}",
                "male_es": cluster.representative_original,
                "female_es": cluster.representative_original.replace("o", "a") if "o" in cluster.representative_original else cluster.representative_original + "a",
                "category": "Professional",
            })

        # Create a result for this request with the correct custom_id
        # Note: cluster IDs for stragglers are still in results but marked missing
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

    # Complete the first batch with straggler results
    fake_anthropic.complete_batch(batch_id, results)

    # Create worker and tick to process the batch (should detect stragglers and submit retry)
    db_factory = get_temp_db_factory(temp_db)
    worker = Worker(client=fake_anthropic, db_factory=db_factory)
    asyncio.run(worker.tick())

    # Verify job is now in retrying state and a second batch exists
    conn2 = sqlite3.connect(temp_db, isolation_level=None)
    conn2.row_factory = sqlite3.Row
    job = jobs_dao.get_job(conn2, preview.job_id)
    assert job.status in {"retrying", "submitted"}  # May have moved to submitted

    batches_after = batches_dao.list_batches_for_job(conn2, preview.job_id)
    assert len(batches_after) == 2  # Original + retry batch

    # Find the retry batch (round 1)
    retry_batch = next((b for b in batches_after if b.retry_round == 1), None)
    assert retry_batch is not None, "Retry batch not found"
    retry_batch_id = retry_batch.id

    # Get retry requests
    retry_requests = batch_requests_dao.list_requests_for_batch(conn2, retry_batch_id)
    assert len(retry_requests) > 0

    # Get the straggler cluster (the one at index 4 from original)
    original_clusters = clusters_dao.list_clusters(conn2, preview.job_id)
    # Find the cluster that's still unresolved (no answer)
    unresolved_clusters = [c for c in original_clusters if c.male_es is None]
    assert len(unresolved_clusters) == 1, "Should have exactly 1 unresolved cluster (the straggler)"

    # Build results for the retry batch with the missing cluster
    retry_results = []
    for req in retry_requests:
        cluster_ids = req.cluster_ids
        cluster_results = []
        for cluster_idx, cluster_id in enumerate(cluster_ids):
            cluster = next((c for c in original_clusters if c.id == cluster_id), None)
            assert cluster is not None
            cluster_results.append({
                "id": f"t{(cluster_idx + 1):03d}",
                "male_es": cluster.representative_original,
                "female_es": cluster.representative_original.replace("o", "a") if "o" in cluster.representative_original else cluster.representative_original + "a",
                "category": "Professional",
            })

        retry_results.append({
            "custom_id": req.id,
            "result": {
                "message": {
                    "usage": {"input_tokens": 100, "output_tokens": 50},
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

    conn2.close()

    # Complete the retry batch
    fake_anthropic.complete_batch(retry_batch_id, retry_results)

    # Worker tick again to process retry batch
    asyncio.run(worker.tick())

    # Verify job completed and all clusters populated
    conn3 = sqlite3.connect(temp_db, isolation_level=None)
    conn3.row_factory = sqlite3.Row
    job_final = jobs_dao.get_job(conn3, preview.job_id)
    assert job_final.status == "completed"

    # Verify all clusters have answers
    clusters_final = clusters_dao.list_clusters(conn3, preview.job_id)
    for cluster in clusters_final:
        assert cluster.male_es is not None, f"Cluster {cluster.id} missing male_es"
        assert cluster.female_es is not None, f"Cluster {cluster.id} missing female_es"
        assert cluster.category is not None, f"Cluster {cluster.id} missing category"
        assert cluster.error is None, f"Cluster {cluster.id} has error: {cluster.error}"

    conn3.close()


def test_e2e_two_batch_rows_after_retry(temp_db, fake_anthropic):
    """Verify that retry creates a second batch row with correct parent_batch_id."""
    # Create input
    titles = """Jefe de Compras
Jefe Compras
Ingeniero de Software
Ingeniero Software
Gerente de Producto
Gerente Producto
VP de Ventas
Vicepresidente de Ventas
Director de Finanzas
Director Finanzas"""

    # Create connection and job
    conn = sqlite3.connect(temp_db, isolation_level=None)
    conn.row_factory = sqlite3.Row

    # Create preview job
    preview = create_preview_job(
        conn,
        text=titles,
        threshold=90,
        titles_per_request=10,
    )

    # Commit the job
    commit_job(conn, fake_anthropic, preview.job_id, taxonomy=None, prompt_override=None)

    # Get batch and request info
    batches = batches_dao.list_batches_for_job(conn, preview.job_id)
    batch_id = batches[0].id
    original_batch = batches[0]

    requests = batch_requests_dao.list_requests_for_batch(conn, batch_id)
    clusters = clusters_dao.list_clusters(conn, preview.job_id)

    # Build results with straggler (skip cluster at index 2)
    results = []
    for req in requests:
        cluster_ids = req.cluster_ids
        cluster_results = []
        for cluster_idx, cluster_id in enumerate(cluster_ids):
            if cluster_idx == 2:  # Skip 3rd cluster
                continue
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

    conn.close()

    # Complete first batch with straggler
    fake_anthropic.complete_batch(batch_id, results)

    # Worker tick - should submit retry
    db_factory = get_temp_db_factory(temp_db)
    worker = Worker(client=fake_anthropic, db_factory=db_factory)
    asyncio.run(worker.tick())

    # Verify 2 batches exist
    conn2 = sqlite3.connect(temp_db, isolation_level=None)
    conn2.row_factory = sqlite3.Row
    batches_after = batches_dao.list_batches_for_job(conn2, preview.job_id)
    assert len(batches_after) == 2

    # Verify parent_batch_id relationship
    retry_batch = next((b for b in batches_after if b.retry_round == 1), None)
    assert retry_batch is not None
    assert retry_batch.parent_batch_id == original_batch.id

    # Complete the retry batch
    retry_requests = batch_requests_dao.list_requests_for_batch(conn2, retry_batch.id)
    clusters_again = clusters_dao.list_clusters(conn2, preview.job_id)

    retry_results = []
    for req in retry_requests:
        cluster_ids = req.cluster_ids
        cluster_results = []
        for cluster_idx, cluster_id in enumerate(cluster_ids):
            cluster = next((c for c in clusters_again if c.id == cluster_id), None)
            assert cluster is not None
            cluster_results.append({
                "id": f"t{(cluster_idx + 1):03d}",
                "male_es": cluster.representative_original,
                "female_es": cluster.representative_original.replace("o", "a") if "o" in cluster.representative_original else cluster.representative_original + "a",
                "category": "Professional",
            })

        retry_results.append({
            "custom_id": req.id,
            "result": {
                "message": {
                    "usage": {"input_tokens": 100, "output_tokens": 50},
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

    conn2.close()

    fake_anthropic.complete_batch(retry_batch.id, retry_results)
    asyncio.run(worker.tick())

    # Final verification: still 2 batches, job completed
    conn3 = sqlite3.connect(temp_db, isolation_level=None)
    conn3.row_factory = sqlite3.Row
    batches_final = batches_dao.list_batches_for_job(conn3, preview.job_id)
    assert len(batches_final) == 2

    job_final = jobs_dao.get_job(conn3, preview.job_id)
    assert job_final.status == "completed"
    conn3.close()


def test_e2e_final_state_is_completed_not_failed(temp_db, fake_anthropic):
    """Verify that successful straggler recovery results in completed state, not failed."""
    # Create input
    titles = """Jefe de Compras
Jefe Compras
Ingeniero de Software
Ingeniero Software
Gerente de Producto
Gerente Producto
VP de Ventas
Vicepresidente de Ventas
Director de Finanzas
Director Finanzas"""

    # Create connection and job
    conn = sqlite3.connect(temp_db, isolation_level=None)
    conn.row_factory = sqlite3.Row

    # Create preview job
    preview = create_preview_job(
        conn,
        text=titles,
        threshold=90,
        titles_per_request=10,
    )

    # Commit the job
    commit_job(conn, fake_anthropic, preview.job_id, taxonomy=None, prompt_override=None)

    # Get batch and request info
    batches = batches_dao.list_batches_for_job(conn, preview.job_id)
    batch_id = batches[0].id

    requests = batch_requests_dao.list_requests_for_batch(conn, batch_id)
    clusters = clusters_dao.list_clusters(conn, preview.job_id)

    # Build results with straggler (skip cluster at index 1)
    results = []
    for req in requests:
        cluster_ids = req.cluster_ids
        cluster_results = []
        for cluster_idx, cluster_id in enumerate(cluster_ids):
            if cluster_idx == 1:  # Skip 2nd cluster
                continue
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

    conn.close()

    # Complete first batch with straggler
    fake_anthropic.complete_batch(batch_id, results)

    # Worker tick - should submit retry
    db_factory = get_temp_db_factory(temp_db)
    worker = Worker(client=fake_anthropic, db_factory=db_factory)
    asyncio.run(worker.tick())

    # Get retry batch
    conn2 = sqlite3.connect(temp_db, isolation_level=None)
    conn2.row_factory = sqlite3.Row
    batches_after = batches_dao.list_batches_for_job(conn2, preview.job_id)
    retry_batch = next((b for b in batches_after if b.retry_round == 1), None)
    assert retry_batch is not None

    # Complete the retry batch
    retry_requests = batch_requests_dao.list_requests_for_batch(conn2, retry_batch.id)
    clusters_again = clusters_dao.list_clusters(conn2, preview.job_id)

    retry_results = []
    for req in retry_requests:
        cluster_ids = req.cluster_ids
        cluster_results = []
        for cluster_idx, cluster_id in enumerate(cluster_ids):
            cluster = next((c for c in clusters_again if c.id == cluster_id), None)
            assert cluster is not None
            cluster_results.append({
                "id": f"t{(cluster_idx + 1):03d}",
                "male_es": cluster.representative_original,
                "female_es": cluster.representative_original.replace("o", "a") if "o" in cluster.representative_original else cluster.representative_original + "a",
                "category": "Professional",
            })

        retry_results.append({
            "custom_id": req.id,
            "result": {
                "message": {
                    "usage": {"input_tokens": 100, "output_tokens": 50},
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

    conn2.close()

    fake_anthropic.complete_batch(retry_batch.id, retry_results)
    asyncio.run(worker.tick())

    # Final verification: job is completed, not failed
    conn3 = sqlite3.connect(temp_db, isolation_level=None)
    conn3.row_factory = sqlite3.Row
    job_final = jobs_dao.get_job(conn3, preview.job_id)
    assert job_final.status == "completed", f"Job should be completed, got {job_final.status}"
    assert job_final.error_rows == 0, f"Job should have 0 error rows, got {job_final.error_rows}"

    # Verify all clusters populated
    clusters_final = clusters_dao.list_clusters(conn3, preview.job_id)
    for cluster in clusters_final:
        assert cluster.male_es is not None, f"Cluster {cluster.id} missing male_es"
        assert cluster.female_es is not None, f"Cluster {cluster.id} missing female_es"
        assert cluster.category is not None, f"Cluster {cluster.id} missing category"
        assert cluster.error is None, f"Cluster {cluster.id} has error: {cluster.error}"

    conn3.close()
