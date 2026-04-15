# 02 — Data Model and DAO Layer

Build the SQLite schema, the migration runner, and a thin DAO module per table. Every function is typed, parameterized, and unit-tested against an in-memory SQLite database. No business logic.

Reference: `spec/05-data-model.md`.

---

### P02-01 — Migration runner

**Deps:** P01-02, P01-03
**Files:** `backend/app/db.py`, `backend/tests/test_db.py`
**Goal:** A connection factory that applies pending SQL migrations on first use, idempotently.

**Implementation:**
```python
# backend/app/db.py
import sqlite3
from pathlib import Path
from .settings import settings

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.database_path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    _apply_migrations(conn)
    return conn

def _apply_migrations(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at INTEGER NOT NULL
        )
    """)
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_version")}
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = int(path.name.split("_")[0])
        if version in applied:
            continue
        sql = path.read_text()
        conn.executescript(sql)
        conn.execute("INSERT INTO schema_version VALUES (?, unixepoch())", (version,))
```

**Test:** `cd backend && uv run pytest tests/test_db.py -v`

Required assertions:
- `test_get_connection_creates_schema_version_table`
- `test_applying_migrations_is_idempotent` — call `get_connection()` twice, assert `schema_version` has same count.
- `test_foreign_keys_enabled` — assert `PRAGMA foreign_keys` returns 1.
- `test_journal_mode_is_wal` — assert `PRAGMA journal_mode` returns `"wal"`.

**Done when:**
- [ ] All 4 tests pass with a tmp-path DB.

---

### P02-02 — Initial migration SQL

**Deps:** P02-01
**Files:** `backend/app/migrations/001_initial.sql`
**Goal:** Paste the full DDL from `spec/05-data-model.md` into the migration file verbatim, plus the `task_templates` seed row with a **placeholder** `system_prompt` (the real prompt is filled in P05-02).

**Implementation:** copy from `spec/05-data-model.md` section "Full DDL". For the seed insert, use `system_prompt = 'PLACEHOLDER'` and `few_shots = '[]'`. The `jobs` CREATE TABLE must include the three additional columns after `titles_per_request`: `row_subset_mode TEXT NOT NULL DEFAULT 'all'`, `row_subset_n INTEGER`, `is_dry_run INTEGER NOT NULL DEFAULT 0`.

**Test:** `cd backend && uv run pytest tests/test_db.py::test_initial_migration -v`

Required assertions (add to `test_db.py`):
- `test_initial_migration_creates_all_tables` — query `sqlite_master` for each of: `task_templates`, `jobs`, `job_rows`, `clusters`, `batches`, `batch_requests`, `spend_log`, `sessions`. Also assert that `jobs` has columns `row_subset_mode`, `row_subset_n`, and `is_dry_run`.
- `test_initial_migration_seeds_job_titles_es` — `SELECT COUNT(*) FROM task_templates WHERE id = 'job_titles_es'` returns 1.
- `test_initial_migration_creates_expected_indexes` — query `sqlite_master WHERE type='index'` and assert the 6 indexes from spec exist.

**Done when:**
- [ ] All 3 tests pass.

---

### P02-03 — DB connection dependency for FastAPI

**Deps:** P02-01
**Files:** `backend/app/db.py` (extend), `backend/tests/test_db_dependency.py`
**Goal:** Expose a FastAPI dependency that yields a per-request SQLite connection and closes it on teardown.

**Implementation:**
```python
# append to db.py
from typing import Generator
def db_dep() -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
```

**Test:** `cd backend && uv run pytest tests/test_db_dependency.py -v`

Required assertions:
- `test_db_dep_yields_working_connection` — use it in a tiny FastAPI route + `TestClient`, assert a `SELECT 1` runs.
- `test_db_dep_closes_on_exception` — wrap the yielded conn with a mock and assert close called.

**Done when:**
- [ ] Both tests pass.

---

### P02-04 — DAO: task_templates

**Deps:** P02-02
**Files:** `backend/app/dao/task_templates.py`, `backend/tests/dao/test_task_templates.py`
**Goal:** Read-only DAO to fetch a task template by id.

**Implementation:**
```python
from sqlite3 import Connection
from dataclasses import dataclass
import json

@dataclass(frozen=True)
class TaskTemplate:
    id: str
    name: str
    system_prompt: str
    few_shots: list
    output_columns: list[str]
    default_titles_per_request: int

def get_template(conn: Connection, template_id: str) -> TaskTemplate | None:
    row = conn.execute("SELECT * FROM task_templates WHERE id = ?", (template_id,)).fetchone()
    if row is None:
        return None
    return TaskTemplate(
        id=row["id"],
        name=row["name"],
        system_prompt=row["system_prompt"],
        few_shots=json.loads(row["few_shots"]),
        output_columns=json.loads(row["output_columns"]),
        default_titles_per_request=row["default_titles_per_request"],
    )
```

**Test:** `cd backend && uv run pytest tests/dao/test_task_templates.py -v`

Required assertions:
- `test_get_template_returns_seed_row` — fetches `job_titles_es`, asserts `name` and types.
- `test_get_template_nonexistent_returns_none`
- `test_get_template_parses_json_fields`

**Done when:**
- [ ] All 3 tests pass.

---

### P02-05 — DAO: jobs

**Deps:** P02-02
**Files:** `backend/app/dao/jobs.py`, `backend/tests/dao/test_jobs.py`
**Goal:** Create / read / list / update functions for the `jobs` table.

**Implementation:**
Functions to implement:
- `create_job(conn, *, task_template_id: str, fuzzy_threshold: int, titles_per_request: int, row_subset_mode: str = "all", row_subset_n: int | None = None, is_dry_run: bool = False) -> str` — returns new UUID.
- `get_job(conn, job_id: str) -> Job | None`
- `list_jobs(conn) -> list[Job]` — ordered by `created_at DESC`.
- `update_job_status(conn, job_id: str, new_status: str) -> None`
- `update_job_counts(conn, job_id: str, **counts) -> None` — accepts `total_rows`, `exact_unique_rows`, `cluster_count`, `completed_rows`, `error_rows`, `est_cost_usd`, `actual_cost_usd`, `finished_at`.
- `count_active_jobs(conn) -> int` — `WHERE status IN ('queued','submitted','polling','retrying')`.

Define `Job` as a `@dataclass(frozen=True)` mirroring the table, including fields `row_subset_mode: str`, `row_subset_n: int | None`, and `is_dry_run: bool`.

**Test:** `cd backend && uv run pytest tests/dao/test_jobs.py -v`

Required assertions:
- `test_create_job_returns_valid_uuid` — `len == 36`, parseable by `uuid.UUID`.
- `test_get_job_after_create_roundtrips`
- `test_list_jobs_ordered_newest_first`
- `test_update_job_status_persists`
- `test_update_job_counts_persists_all_fields`
- `test_count_active_jobs_ignores_terminal_states`
- `test_get_nonexistent_job_returns_none`
- `test_create_job_with_row_subset_params` — create with `row_subset_mode="first_n"`, `row_subset_n=500`; assert roundtrip preserves both values.
- `test_create_job_with_dry_run_flag` — create with `is_dry_run=True`; assert roundtrip preserves value.

**Done when:**
- [ ] All 9 tests pass.

---

### P02-06 — DAO: job_rows

**Deps:** P02-02
**Files:** `backend/app/dao/job_rows.py`, `backend/tests/dao/test_job_rows.py`
**Goal:** Bulk insert and cluster assignment for job_rows.

**Implementation:**
Functions:
- `bulk_insert_rows(conn, job_id: str, rows: list[tuple[int, str, str]]) -> None` — each tuple is `(row_index, original, normalized)`.
- `list_rows(conn, job_id: str) -> list[JobRow]`
- `assign_cluster(conn, row_ids: list[int], cluster_id: int, is_representative_row_id: int | None) -> None` — bulk UPDATE.
- `clear_clusters(conn, job_id: str) -> None` — `UPDATE job_rows SET cluster_id = NULL, is_representative = 0 WHERE job_id = ?`.

**Test:** `cd backend && uv run pytest tests/dao/test_job_rows.py -v`

Required assertions:
- `test_bulk_insert_preserves_row_index_order`
- `test_list_rows_returns_ordered_by_row_index`
- `test_assign_cluster_marks_representative_correctly`
- `test_clear_clusters_nulls_cluster_id`
- `test_bulk_insert_10000_rows_under_2s` — performance guard.

**Done when:**
- [ ] All 5 tests pass.

---

### P02-07 — DAO: clusters

**Deps:** P02-02
**Files:** `backend/app/dao/clusters.py`, `backend/tests/dao/test_clusters.py`
**Goal:** CRUD for the `clusters` table.

**Implementation:**
Functions:
- `insert_cluster(conn, *, job_id, representative_original, normalized_key, member_count) -> int` — returns new cluster id.
- `delete_clusters_for_job(conn, job_id) -> None`
- `update_cluster_answers(conn, cluster_id, male_es, female_es, category) -> None`
- `mark_cluster_error(conn, cluster_id, error_code: str) -> None`
- `list_clusters(conn, job_id) -> list[Cluster]`
- `count_unresolved_clusters(conn, job_id) -> int` — where all of `male_es`, `female_es`, `category`, `error` are NULL.

**Test:** `cd backend && uv run pytest tests/dao/test_clusters.py -v`

Required assertions:
- `test_insert_cluster_returns_id`
- `test_update_cluster_answers_persists`
- `test_mark_cluster_error_persists`
- `test_delete_clusters_for_job_removes_all`
- `test_count_unresolved_clusters_after_answer_drops_count`

**Done when:**
- [ ] All 5 tests pass.

---

### P02-08 — DAO: batches

**Deps:** P02-02
**Files:** `backend/app/dao/batches.py`, `backend/tests/dao/test_batches.py`
**Goal:** CRUD for `batches` table.

**Implementation:**
Functions:
- `insert_batch(conn, *, id: str, job_id: str, retry_round: int, parent_batch_id: str | None, status: str, request_count: int) -> None`
- `get_batch(conn, batch_id: str) -> Batch | None`
- `update_batch_status(conn, batch_id: str, status: str, polled_at: int | None = None, completed_at: int | None = None) -> None`
- `list_batches_for_job(conn, job_id: str) -> list[Batch]` — ordered by `retry_round` ASC.
- `list_non_terminal_batches(conn) -> list[Batch]` — joined with jobs where job status is non-terminal.

**Test:** `cd backend && uv run pytest tests/dao/test_batches.py -v`

Required assertions:
- `test_insert_and_get_roundtrips`
- `test_update_batch_status_sets_timestamps`
- `test_list_batches_for_job_ordered_by_round`
- `test_list_non_terminal_batches_excludes_completed_jobs`

**Done when:**
- [ ] All 4 tests pass.

---

### P02-09 — DAO: batch_requests

**Deps:** P02-02
**Files:** `backend/app/dao/batch_requests.py`, `backend/tests/dao/test_batch_requests.py`
**Goal:** CRUD for `batch_requests` table. `cluster_ids` is stored as JSON text.

**Implementation:**
Functions:
- `insert_request(conn, *, id: str, batch_id: str, cluster_ids: list[int]) -> None` — serializes cluster_ids to JSON.
- `list_requests_for_batch(conn, batch_id: str) -> list[BatchRequest]` — deserializes cluster_ids.
- `mark_request_completed(conn, request_id: str, raw_response: str) -> None`
- `mark_request_failed(conn, request_id: str, error: str, raw_response: str | None = None) -> None`
- `mark_request_missing(conn, request_id: str) -> None`
- `list_pending_requests(conn, batch_id: str) -> list[BatchRequest]`

**Test:** `cd backend && uv run pytest tests/dao/test_batch_requests.py -v`

Required assertions:
- `test_insert_serializes_cluster_ids_as_json`
- `test_list_requests_deserializes_cluster_ids`
- `test_mark_request_completed_updates_status`
- `test_mark_request_failed_sets_error`
- `test_list_pending_requests_filters_by_status`

**Done when:**
- [ ] All 5 tests pass.

---

### P02-10 — DAO: spend_log

**Deps:** P02-02
**Files:** `backend/app/dao/spend_log.py`, `backend/tests/dao/test_spend_log.py`
**Goal:** Append-only spend log + rolling 30-day sum.

**Implementation:**
Functions:
- `insert_spend(conn, *, job_id: str, batch_id: str | None, usd: float, at: int) -> None`
- `sum_last_30_days(conn, now: int | None = None) -> float` — `SELECT COALESCE(SUM(usd), 0) FROM spend_log WHERE at > :cutoff`; if `now` is None, use `time.time()`.
- `reset_date_approx(conn, now: int | None = None) -> int | None` — returns the UNIX timestamp of `min(at) + 30*86400` for rows still in window; None if no rows.

**Test:** `cd backend && uv run pytest tests/dao/test_spend_log.py -v`

Required assertions:
- `test_insert_spend_persists`
- `test_sum_last_30_days_excludes_old_entries`
- `test_sum_last_30_days_returns_zero_when_empty`
- `test_reset_date_approx_returns_oldest_plus_30`

**Done when:**
- [ ] All 4 tests pass.

---

### P02-11 — DAO: sessions

**Deps:** P02-02
**Files:** `backend/app/dao/sessions.py`, `backend/tests/dao/test_sessions.py`
**Goal:** Session CRUD + lazy expired cleanup.

**Implementation:**
Functions:
- `create_session(conn, *, session_id_hash: str, ttl_seconds: int = 2592000) -> None`
- `get_valid_session(conn, session_id_hash: str, now: int | None = None) -> Session | None` — returns None if expired.
- `delete_session(conn, session_id_hash: str) -> None`
- `purge_expired(conn, now: int | None = None) -> int` — returns count purged.

**Test:** `cd backend && uv run pytest tests/dao/test_sessions.py -v`

Required assertions:
- `test_create_and_get_roundtrips`
- `test_get_valid_session_returns_none_if_expired`
- `test_delete_session_removes_row`
- `test_purge_expired_counts_and_removes`

**Done when:**
- [ ] All 4 tests pass.

---

### P02-12 — Test fixtures: in-memory DB

**Deps:** P02-01
**Files:** `backend/tests/conftest.py`
**Goal:** A `pytest` fixture that yields a fresh in-memory SQLite connection with all migrations applied, so every DAO test starts clean.

**Implementation:**
```python
import pytest
import sqlite3
from app.db import _apply_migrations

@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:", isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode = WAL")
    c.execute("PRAGMA foreign_keys = ON")
    _apply_migrations(c)
    yield c
    c.close()
```

**Test:** `cd backend && uv run pytest tests/dao/ -v`

Required assertions:
- All DAO tests from P02-04 through P02-11 pass using this fixture.

**Done when:**
- [ ] Total DAO test count ≥ 40 (sum from P02-04..11), all passing.
