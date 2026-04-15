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
