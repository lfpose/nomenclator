import sqlite3
import tempfile

import pytest

from app.db import get_connection


def test_get_connection_creates_schema_version_table():
    """Test that get_connection creates the schema_version table."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = f"{tmpdir}/test.db"
        # Monkey patch settings.database_path
        import app.settings
        original_path = app.settings.settings.database_path
        app.settings.settings.database_path = db_path

        try:
            conn = get_connection()
            result = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
            ).fetchone()
            assert result is not None
            assert result["name"] == "schema_version"
        finally:
            app.settings.settings.database_path = original_path


def test_applying_migrations_is_idempotent():
    """Test that calling get_connection twice doesn't duplicate migrations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = f"{tmpdir}/test.db"
        import app.settings
        original_path = app.settings.settings.database_path
        app.settings.settings.database_path = db_path

        try:
            # First connection
            conn1 = get_connection()
            count1 = conn1.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
            conn1.close()

            # Second connection
            conn2 = get_connection()
            count2 = conn2.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
            conn2.close()

            assert count1 == count2
        finally:
            app.settings.settings.database_path = original_path


def test_foreign_keys_enabled():
    """Test that foreign_keys pragma is set to ON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = f"{tmpdir}/test.db"
        import app.settings
        original_path = app.settings.settings.database_path
        app.settings.settings.database_path = db_path

        try:
            conn = get_connection()
            result = conn.execute("PRAGMA foreign_keys").fetchone()
            assert result[0] == 1
        finally:
            app.settings.settings.database_path = original_path


def test_journal_mode_is_wal():
    """Test that journal_mode pragma is set to WAL."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = f"{tmpdir}/test.db"
        import app.settings
        original_path = app.settings.settings.database_path
        app.settings.settings.database_path = db_path

        try:
            conn = get_connection()
            result = conn.execute("PRAGMA journal_mode").fetchone()
            assert result[0] == "wal"
        finally:
            app.settings.settings.database_path = original_path


def test_initial_migration_creates_all_tables():
    """Test that initial migration creates all expected tables with required columns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = f"{tmpdir}/test.db"
        import app.settings
        original_path = app.settings.settings.database_path
        app.settings.settings.database_path = db_path

        try:
            conn = get_connection()
            
            # Check all tables exist
            expected_tables = [
                'task_templates', 'jobs', 'job_rows', 'clusters',
                'batches', 'batch_requests', 'spend_log', 'sessions'
            ]
            for table in expected_tables:
                result = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,)
                ).fetchone()
                assert result is not None, f"Table {table} not found"
            
            # Check jobs table has row_subset_mode, row_subset_n, and is_dry_run columns
            jobs_columns = conn.execute("PRAGMA table_info(jobs)").fetchall()
            column_names = {col[1] for col in jobs_columns}
            assert 'row_subset_mode' in column_names
            assert 'row_subset_n' in column_names
            assert 'is_dry_run' in column_names
        finally:
            app.settings.settings.database_path = original_path


def test_initial_migration_seeds_job_titles_es():
    """Test that initial migration seeds the job_titles_es task template."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = f"{tmpdir}/test.db"
        import app.settings
        original_path = app.settings.settings.database_path
        app.settings.settings.database_path = db_path

        try:
            conn = get_connection()
            count = conn.execute(
                "SELECT COUNT(*) FROM task_templates WHERE id = 'job_titles_es'"
            ).fetchone()[0]
            assert count == 1
            
            row = conn.execute(
                "SELECT system_prompt FROM task_templates WHERE id = 'job_titles_es'"
            ).fetchone()
            assert row['system_prompt'] is not None and row['system_prompt'] != ''
        finally:
            app.settings.settings.database_path = original_path


def test_initial_migration_creates_expected_indexes():
    """Test that initial migration creates all expected indexes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = f"{tmpdir}/test.db"
        import app.settings
        original_path = app.settings.settings.database_path
        app.settings.settings.database_path = db_path

        try:
            conn = get_connection()
            
            # Expected indexes from spec
            expected_indexes = [
                'idx_jobs_status_created',
                'idx_job_rows_job_order',
                'idx_job_rows_cluster',
                'idx_clusters_job',
                'idx_batches_job',
                'idx_batch_requests_batch',
                'idx_spend_log_at',
                'idx_sessions_expires',
            ]
            
            for index_name in expected_indexes:
                result = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                    (index_name,)
                ).fetchone()
                assert result is not None, f"Index {index_name} not found"
        finally:
            app.settings.settings.database_path = original_path
