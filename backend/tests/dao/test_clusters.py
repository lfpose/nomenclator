import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def conn():
    """Create an in-memory SQLite connection with all migrations applied."""
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    # Apply migrations
    migrations_dir = Path(__file__).parent.parent.parent / "app" / "migrations"
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at INTEGER NOT NULL
        )
    """)

    for path in sorted(migrations_dir.glob("*.sql")):
        version = int(path.name.split("_")[0])
        if conn.execute("SELECT 1 FROM schema_version WHERE version = ?", (version,)).fetchone():
            continue
        sql = path.read_text()
        conn.executescript(sql)
        conn.execute("INSERT INTO schema_version VALUES (?, unixepoch())", (version,))

    yield conn
    conn.close()


def test_insert_cluster_returns_id(conn):
    """Test that insert_cluster returns the new cluster ID."""
    from backend.app.dao.jobs import create_job

    job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )

    cluster_id = conn.execute(
        """
        INSERT INTO clusters (job_id, representative_original, normalized_key, member_count)
        VALUES (?, ?, ?, ?)
        """,
        (job_id, "Jefe de Compras", "jefe de compras", 5),
    ).lastrowid

    assert cluster_id == 1

    # Test using the actual function
    from backend.app.dao.clusters import insert_cluster

    new_id = insert_cluster(
        conn,
        job_id=job_id,
        representative_original="Analista de Ventas",
        normalized_key="analista de ventas",
        member_count=3,
    )

    assert new_id == 2


def test_update_cluster_answers_persists(conn):
    """Test that update_cluster_answers persists values."""
    from backend.app.dao.clusters import insert_cluster, update_cluster_answers
    from backend.app.dao.jobs import create_job

    job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )

    cluster_id = insert_cluster(
        conn,
        job_id=job_id,
        representative_original="Jefe de Compras",
        normalized_key="jefe de compras",
        member_count=5,
    )

    update_cluster_answers(
        conn,
        cluster_id=cluster_id,
        male_es="Jefe de Compras",
        female_es="Jefa de Compras",
        category="Management",
    )

    row = conn.execute("SELECT * FROM clusters WHERE id = ?", (cluster_id,)).fetchone()
    assert row["male_es"] == "Jefe de Compras"
    assert row["female_es"] == "Jefa de Compras"
    assert row["category"] == "Management"


def test_mark_cluster_error_persists(conn):
    """Test that mark_cluster_error persists error code."""
    from backend.app.dao.clusters import insert_cluster, mark_cluster_error
    from backend.app.dao.jobs import create_job

    job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )

    cluster_id = insert_cluster(
        conn,
        job_id=job_id,
        representative_original="Jefe de Compras",
        normalized_key="jefe de compras",
        member_count=5,
    )

    mark_cluster_error(conn, cluster_id=cluster_id, error_code="max_retries_exceeded")

    row = conn.execute("SELECT * FROM clusters WHERE id = ?", (cluster_id,)).fetchone()
    assert row["error"] == "max_retries_exceeded"


def test_delete_clusters_for_job_removes_all(conn):
    """Test that delete_clusters_for_job removes all clusters."""
    from backend.app.dao.clusters import delete_clusters_for_job, insert_cluster
    from backend.app.dao.jobs import create_job

    job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )

    insert_cluster(
        conn,
        job_id=job_id,
        representative_original="Jefe de Compras",
        normalized_key="jefe de compras",
        member_count=5,
    )
    insert_cluster(
        conn,
        job_id=job_id,
        representative_original="Analista de Ventas",
        normalized_key="analista de ventas",
        member_count=3,
    )

    count_before = conn.execute("SELECT COUNT(*) FROM clusters WHERE job_id = ?", (job_id,)).fetchone()[0]
    assert count_before == 2

    delete_clusters_for_job(conn, job_id=job_id)

    count_after = conn.execute("SELECT COUNT(*) FROM clusters WHERE job_id = ?", (job_id,)).fetchone()[0]
    assert count_after == 0


def test_count_unresolved_clusters_after_answer_drops_count(conn):
    """Test that count_unresolved_clusters decreases after answers are set."""
    from backend.app.dao.clusters import (
        count_unresolved_clusters,
        insert_cluster,
        update_cluster_answers,
    )
    from backend.app.dao.jobs import create_job

    job_id = create_job(
        conn,
        task_template_id="job_titles_es",
        fuzzy_threshold=90,
        titles_per_request=25,
    )

    insert_cluster(
        conn,
        job_id=job_id,
        representative_original="Jefe de Compras",
        normalized_key="jefe de compras",
        member_count=5,
    )
    insert_cluster(
        conn,
        job_id=job_id,
        representative_original="Analista de Ventas",
        normalized_key="analista de ventas",
        member_count=3,
    )
    insert_cluster(
        conn,
        job_id=job_id,
        representative_original="Gerente de Marketing",
        normalized_key="gerente de marketing",
        member_count=2,
    )

    count = count_unresolved_clusters(conn, job_id=job_id)
    assert count == 3

    # Update one cluster with answers
    cluster_id_1 = conn.execute(
        "SELECT id FROM clusters WHERE representative_original = ?",
        ("Jefe de Compras",),
    ).fetchone()[0]

    update_cluster_answers(
        conn,
        cluster_id=cluster_id_1,
        male_es="Jefe de Compras",
        female_es="Jefa de Compras",
        category="Management",
    )

    count = count_unresolved_clusters(conn, job_id=job_id)
    assert count == 2
