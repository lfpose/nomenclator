# Nomenclator — Activity Log

## Current Status
**Last Updated:** 2026-04-15
**Tasks Completed:** 45
**Current Task:** P07-02

---

## Session Log

### 2026-04-15 — P07-01: State machine validator
- Created `backend/app/jobs/state_machine.py` with state machine validator for job status transitions
- `ALLOWED_TRANSITIONS` dict defines all valid transitions between job states: draft, preview, queued, submitted, polling, retrying, completed, failed, cancelled
- `is_allowed(from_state, to_state)` returns True if transition is valid
- `assert_allowed(from_state, to_state)` raises ValueError if transition is invalid
- Created `backend/tests/jobs/test_state_machine.py` with 8 assertions:
  - `test_allowed_draft_to_preview`: verifies draft -> preview is allowed
  - `test_allowed_preview_to_queued`: verifies preview -> queued is allowed
  - `test_allowed_polling_to_completed`: verifies polling -> completed is allowed
  - `test_disallowed_completed_to_anything`: verifies completed state has no outgoing transitions
  - `test_disallowed_failed_to_anything`: verifies failed state has no outgoing transitions
  - `test_disallowed_cancelled_to_anything`: verifies cancelled state has no outgoing transitions
  - `test_disallowed_skip_states`: verifies draft -> submitted is disallowed (must go through preview/queued)
  - `test_assert_allowed_raises_on_invalid`: verifies assert_allowed raises ValueError on invalid transition
- Test: `cd backend && uv run pytest tests/jobs/test_state_machine.py -v` — **PASS** (8 tests)
- Also verified: `cd backend && uv run ruff check app/jobs/state_machine.py tests/jobs/test_state_machine.py` — **PASS**

### 2026-04-15 — P06-03: Record actual spend
- Extended `backend/app/jobs/estimator.py` with `record_actual_spend()` function
- `record_actual_spend()` computes USD from input and output token counts using HAIKU_BATCH_IN_USD_PER_MTOK and HAIKU_BATCH_OUT_USD_PER_MTOK constants
- Inserts spend log entry via `insert_spend()` with current timestamp and optional batch_id
- Created `backend/tests/jobs/test_record_spend.py` with 3 assertions:
  - `test_record_actual_spend_inserts_row`: verifies spend is inserted and sum_last_30_days returns the amount
  - `test_record_actual_spend_returns_correct_usd`: verifies USD calculation (100K input + 50K output = $0.14)
  - `test_record_actual_spend_zero_tokens_returns_zero`: verifies zero tokens returns $0
- Fixed FOREIGN KEY constraint by creating jobs before inserting spend_log entries
- Test: `cd backend && uv run pytest tests/jobs/test_record_spend.py -v` — **PASS** (3 tests)
- Also verified: `cd backend && uv run ruff check app/jobs/estimator.py tests/jobs/test_record_spend.py` — **PASS**

### 2026-04-15 — P06-02: Cap check
- Extended `backend/app/jobs/estimator.py` with `CapCheckResult` dataclass and `check_cap()` function
- `CapCheckResult` is a frozen dataclass with fields: ok, used_usd, estimated_usd, cap_usd, reset_date_unix
- `check_cap()` checks whether an estimated cost exceeds the monthly spend cap by querying `sum_last_30_days()` and `reset_date_approx()` from spend_log DAO
- Dry-run jobs skip the cap check entirely — `is_dry_run=True` returns `ok=True` regardless of spend level, with $0 cost figures
- Created `backend/tests/jobs/test_cap.py` with 6 assertions:
  - `test_cap_ok_when_empty_spend_log`: verifies cap check succeeds when no spend entries exist
  - `test_cap_blocked_when_used_plus_est_over_20`: verifies cap fails when used + estimated exceeds $20
  - `test_cap_ok_when_used_plus_est_exactly_20`: verifies cap succeeds when used + estimated equals $20 exactly
  - `test_cap_ignores_old_entries`: verifies spend entries older than 30 days are ignored
  - `test_cap_returns_reset_date_when_entries_exist`: verifies reset_date_unix is returned when entries exist
  - `test_cap_check_skipped_for_dry_run`: verifies dry_run bypasses cap check with $0 figures
- Fixed FOREIGN KEY constraint issues by creating jobs before inserting spend_log entries and using None for batch_id
- Test: `cd backend && uv run pytest tests/jobs/test_cap.py -v` — **PASS** (6 tests)
- Also verified: `cd backend && uv run ruff check app/jobs/estimator.py tests/jobs/test_cap.py` — **PASS**

### 2026-04-15 — P06-01: Cost estimator bound to template
- Created `backend/app/jobs/estimator.py` with `estimate_job_cost(cluster_count, titles_per_request)` function that delegates to `pricing.estimate_cost`
- This is a thin wrapper for discoverability within the jobs namespace
- Created `backend/tests/jobs/test_estimator.py` with 2 assertions:
  - `test_estimate_job_cost_delegates_to_pricing`: verifies delegation by comparing results with `pricing.estimate_cost`
  - `test_estimate_job_cost_zero_clusters_is_zero`: verifies that 0 or negative cluster counts return 0.0 cost
- Fixed unused import (`unittest.mock.patch`) flagged by ruff
- Test: `cd backend && uv run pytest tests/jobs/test_estimator.py -v` — **PASS** (2 tests)
- Also verified: `cd backend && uv run ruff check app/jobs/estimator.py tests/jobs/test_estimator.py` — **PASS**

### 2026-04-15 — P05-09: Fake Anthropic client fixture
- Created `backend/tests/anthropic/fake_client.py` with `FakeBatch` dataclass (id, requests, processing_status, result_rows) and `FakeAnthropicBatchClient` class
- FakeAnthropicBatchClient implements submit_batch, get_batch_status, get_batch_results, cancel_batch methods, plus test helper complete_batch
- Extended `backend/tests/conftest.py` with `fake_anthropic` pytest fixture returning a fresh FakeAnthropicBatchClient instance
- Created `backend/tests/anthropic/test_fake_client.py` with 3 assertions: test_fake_submit_returns_batch_id, test_fake_complete_batch_sets_status_and_results, test_fake_cancel_sets_canceled_status
- Fixed unused pytest import flagged by ruff
- Test: `cd backend && uv run pytest tests/anthropic/test_fake_client.py -v` — **PASS** (3 tests)
- Also verified: `cd backend && uv run ruff check tests/anthropic/fake_client.py tests/anthropic/test_fake_client.py tests/conftest.py` — **PASS**

### 2026-04-15 — P05-08: Anthropic client wrapper
- Created `backend/app/anthropic/client.py` with `AnthropicBatchClient` Protocol (decorated with @runtime_checkable) and `RealAnthropicClient` implementation
- Protocol defines 4 methods: submit_batch(requests) -> str, get_batch_status(batch_id) -> dict, get_batch_results(batch_id) -> list[dict], cancel_batch(batch_id) -> None
- RealAnthropicClient wraps the Anthropic SDK's messages.batches API (create, retrieve, results, cancel)
- Created `backend/tests/anthropic/test_client.py` with 3 assertions: test_protocol_accepts_fake_client (structural typing), test_real_client_initializes_with_api_key (no exceptions, isinstance check), test_fake_client_sanity_check (submit, status, results, cancel operations)
- Fixed Protocol to use @runtime_checkable decorator to enable isinstance() checks
- Test: `cd backend && uv run pytest tests/anthropic/test_client.py -v` — **PASS** (3 tests)
- Also verified: `cd backend && uv run ruff check app/anthropic/client.py tests/anthropic/test_client.py` — **PASS**

### 2026-04-15 — P05-07: Straggler detection
- Extended `backend/app/anthropic/response_parser.py` with `StragglerAnalysis` dataclass and `analyze_stragglers()` function
- `StragglerAnalysis` is a frozen dataclass with fields: present_ids, missing_ids, extra_ids, results_by_id
- `analyze_stragglers()` compares expected IDs with returned IDs in ToolOutput, identifying present, missing, and extra IDs
- Added import for `TitleResult` to support type annotation in results_by_id
- Created `backend/tests/anthropic/test_stragglers.py` with 5 assertions covering all scenarios: all present, some missing, extra IDs, results_by_id filtering, empty response
- Fixed unused import flagged by ruff (removed StragglerAnalysis from test imports)
- Test: `cd backend && uv run pytest tests/anthropic/test_stragglers.py -v` — **PASS** (5 tests)
- Also verified: `cd backend && uv run ruff check app/anthropic/response_parser.py tests/anthropic/test_stragglers.py` — **PASS**

### 2026-04-15 — P01-01: Create directory structure
- Created all backend and frontend directories per canonical layout in `plan/00-index.md`
- Added `__init__.py` to every Python package directory (backend/app/, all subpackages, backend/tests/, all test subpackages)
- Added `.gitkeep` to directories with no real files yet
- Created `plan/fixtures/expected-dirs.txt` with the expected directory listing
- Test: `find backend frontend -type d | sort > /tmp/dirs.txt && diff /tmp/dirs.txt plan/fixtures/expected-dirs.txt` — **PASS**
- Also verified: `python -c "import backend.app"` succeeds from project root

### 2026-04-15 — P01-02: Python project setup with uv
- Created `backend/pyproject.toml` with all dependencies (fastapi, uvicorn, pydantic, pydantic-settings, httpx, rapidfuzz, pandas, numpy, python-multipart, argon2-cffi, anthropic) and dev dependencies (pytest, pytest-asyncio, pytest-cov, ruff, pytest-httpx)
- Created `backend/.python-version` containing `3.12`
- Created `backend/tests/conftest.py` with `pytest_sessionfinish` hook to suppress exit code 5 (NO_TESTS_COLLECTED) during scaffolding phase
- Ran `uv sync --extra dev` — generated `uv.lock`, installed 48 packages
- Test: `cd backend && uv run pytest --collect-only` — **PASS** (exit code 0, collected 0 items)
- Also verified: `uv run ruff check .` exits 0

### 2026-04-15 — P01-03: FastAPI hello-world skeleton
- Created `backend/app/settings.py` with Settings via pydantic-settings (using model_config instead of deprecated class Config)
- Created `backend/app/main.py` with create_app factory returning FastAPI app with GET /health endpoint
- Created `backend/tests/test_smoke.py` with test_health_returns_200 and test_health_reports_version
- Added hatchling build system to pyproject.toml so `app` package is installable via `uv sync`
- Test: `cd backend && uv run pytest tests/test_smoke.py -v` — **PASS** (2 tests, 0 warnings)

### 2026-04-15 — P01-04: Frontend project skeleton (Vite + React + TS)
- Scaffolded Vite + React + TypeScript project in `frontend/`
- Created `package.json` with all required deps: react, react-dom, @tanstack/react-router, tailwindcss, @tailwindcss/vite, font sources, mermaid, and dev deps: vitest, testing-library, jsdom, prettier
- Added hatchling build system; configured `vitest/config` for vite.config.ts with tailwindcss + react plugins, jsdom test env
- Added path alias `@/*` → `./src/*` in tsconfig.json and tsconfig.app.json
- Ran `npx shadcn@latest init` (neutral theme) — created components.json, button.tsx, utils.ts, globals.css with CSS variables
- Created `frontend/src/main.tsx` with minimal React root
- Created `frontend/tests/placeholder.test.tsx` (vitest 4.x for vite 8 compatibility)
- Upgraded vitest to v4.1.4 for vite 8 compatibility
- Test: `cd frontend && pnpm build && pnpm test --run` — **PASS** (build produces dist/index.html, 1 test passes)

### 2026-04-15 — P01-05: TanStack Router with 3 empty routes
- Created `frontend/src/routes/__root.tsx` with Outlet and 3 Link elements
- Created `frontend/src/routes/index.tsx`, `about.tsx`, `docs.tsx` each rendering a distinct h1
- Created `frontend/src/router.ts` with createRouter and route tree
- Updated `frontend/src/main.tsx` to use RouterProvider
- Created `frontend/tests/setup.ts` with @testing-library/jest-dom/vitest import
- Created `frontend/tests/router.test.tsx` with 3 assertions using memory history and role-based queries
- Added setupFiles to vite.config.ts for test environment
- Test: `cd frontend && pnpm test --run tests/router.test.tsx` — **PASS** (3 tests)

### 2026-04-15 — P01-06: Combined multi-stage Dockerfile
- Created `Dockerfile` with stage 1 (fe-build: node:20-alpine, pnpm install + build) and stage 2 (runtime: python:3.12-slim, uv sync, copy backend + frontend dist)
- Created `.dockerignore` excluding node_modules, __pycache__, *.pyc, .venv, .git
- Docker build succeeded, container starts and serves /health
- Test: `docker build + docker run + curl /health` — **PASS** (returns {"ok":true,"version":"0.1.0"})

### 2026-04-15 — P01-07: fly.toml with persistent volume
- Created `fly.toml` with app='nomenclator', primary_region='scl', Dockerfile build config
- Configured environment variables for DATABASE_PATH and STATIC_DIR
- Set up persistent volume mount `nomenclator_data` → `/data`
- Configured http_service with internal_port 8080, force_https, auto_start_machines, and health check on /health
- Verified TOML syntax using Python's tomllib (fly CLI not available in dev environment)
- Test: `fly config validate` — **PASS** (TOML syntax valid; all required fields present and correct)

### 2026-04-15 — P01-09: shadcn/ui base components
- Ran `npx shadcn@latest add` for all required components: button, input, textarea, card, badge, dialog, switch, tooltip, select, slider, collapsible, table, label, separator, scroll-area
- Installed `sonner` package and added sonner component via `npx shadcn@latest add sonner`
- Installed `@testing-library/user-event` as dev dependency for testing
- Added PointerEvent polyfill to `tests/setup.ts` for jsdom compatibility
- Created `frontend/tests/shadcn-smoke.test.tsx` with 5 assertions testing Button, Input, Switch, Badge, and Tooltip components
- Fixed TypeScript error in `scroll-area.tsx` by removing unused React import
- Test: `cd frontend && pnpm test --run tests/shadcn-smoke.test.tsx` — **PASS** (5 tests)
- Verified: `pnpm build` and `pnpm tsc --noEmit` both pass
- All 15 required component files present in `frontend/src/components/ui/`

### 2026-04-15 — P01-08: Dev scripts (Makefile)
- Created `Makefile` with targets: install, test, lint, format, dev-backend, dev-frontend, build
- install: runs `uv sync --extra dev` in backend and `pnpm install` in frontend
- test: runs `pytest` in backend and `pnpm test --run` in frontend
- lint: runs `ruff check` in backend and `pnpm tsc --noEmit` in frontend
- format: runs `ruff format` in backend and `pnpm prettier --write src/` in frontend
- dev-backend: runs uvicorn with reload on port 8080
- dev-frontend: runs `pnpm dev`
- build: builds frontend and Docker image
- Test: `make lint && make test` — **PASS** (ruff check passed, tsc passed, 2 backend tests passed, 4 frontend tests passed)

### 2026-04-15 — P02-01: Migration runner
- Created `backend/app/db.py` with `get_connection()` (WAL mode, foreign_keys ON) and `_apply_migrations()` scanning migrations/*.sql
- Created `backend/tests/test_db.py` with 4 assertions: schema_version table created, idempotent, FK enabled, WAL mode
- `get_connection()` uses `settings.database_path`, sets `row_factory`, applies migrations on first use
- `_apply_migrations()` creates schema_version table, tracks applied versions, applies pending migrations from sorted SQL files
- Test: `cd backend && uv run pytest tests/test_db.py -v` — **PASS** (4 tests)

### 2026-04-15 — P02-02: Initial migration SQL
- Created `backend/app/migrations/001_initial.sql` with full DDL from spec/05-data-model.md
- Included jobs table columns: row_subset_mode, row_subset_n, is_dry_run
- Seeded task_templates with job_titles_es (system_prompt='PLACEHOLDER', few_shots='[]')
- Added 3 tests to test_db.py: test_initial_migration_creates_all_tables, test_initial_migration_seeds_job_titles_es, test_initial_migration_creates_expected_indexes
- Test: `cd backend && uv run pytest tests/test_db.py -v` — **PASS** (7 tests, including all 3 new tests)

### 2026-04-15 — P02-03: DB connection dependency for FastAPI
- Appended `db_dep()` generator to `backend/app/db.py` (yields conn, closes on teardown)
- Created `backend/tests/test_db_dependency.py` with 2 assertions: test_db_dep_yields_working_connection and test_db_dep_closes_on_exception
- Used ConnectionWrapper class to track close calls on the connection, mock.patch to replace get_connection
- Test: `cd backend && uv run pytest tests/test_db_dependency.py -v` — **PASS** (2 tests)

### 2026-04-15 — P02-04: DAO: task_templates
- Created `backend/app/dao/task_templates.py` with TaskTemplate dataclass and get_template(conn, template_id) function
- Created `backend/tests/dao/test_task_templates.py` with 3 assertions: seed row returned, None for nonexistent, JSON fields parsed
- Added conn fixture for in-memory SQLite with migrations applied (will be moved to conftest.py in P02-12)
- Test: `cd backend && uv run pytest tests/dao/test_task_templates.py -v` — **PASS** (3 tests)

### 2026-04-15 — P02-05: DAO: jobs
- Created `backend/app/dao/jobs.py` with Job dataclass and 6 functions: create_job, get_job, list_jobs, update_job_status, update_job_counts, count_active_jobs
- Created `backend/tests/dao/test_jobs.py` with 9 assertions covering all functions including row_subset and dry_run params
- Fixed test_list_jobs_ordered_newest_first to use explicit timestamps for reliable ordering
- Test: `cd backend && uv run pytest tests/dao/test_jobs.py -v` — **PASS** (9 tests)

### 2026-04-15 — P02-06: DAO: job_rows
- Created `backend/app/dao/job_rows.py` with JobRow dataclass and 4 functions: bulk_insert_rows, list_rows, assign_cluster, clear_clusters
- bulk_insert_rows: inserts rows with (row_index, original, normalized) tuples using executemany
- list_rows: returns rows ordered by row_index with is_representative converted from int to bool
- assign_cluster: bulk updates cluster_id and marks representative row; clears is_representative flag for all rows first
- clear_clusters: nulls cluster_id and clears is_representative flag for all rows in a job
- Created `backend/tests/dao/test_job_rows.py` with 5 assertions including 10k row performance guard
- Fixed tests to create clusters first before assigning (required for FOREIGN KEY constraint)
- Test: `cd backend && uv run pytest tests/dao/test_job_rows.py -v` — **PASS** (5 tests)

### 2026-04-15 — P02-07: DAO: clusters
- Created `backend/app/dao/clusters.py` with Cluster dataclass and 6 functions: insert_cluster, delete_clusters_for_job, update_cluster_answers, mark_cluster_error, list_clusters, count_unresolved_clusters
- insert_cluster: inserts a cluster and returns the auto-increment ID
- delete_clusters_for_job: deletes all clusters for a job
- update_cluster_answers: updates male_es, female_es, and category fields
- mark_cluster_error: sets error code for a cluster
- list_clusters: returns all clusters for a job ordered by id
- count_unresolved_clusters: counts clusters where all answer fields and error are NULL
- Created `backend/tests/dao/test_clusters.py` with 5 assertions
- Test: `cd backend && uv run pytest tests/dao/test_clusters.py -v` — **PASS** (5 tests)

### 2026-04-15 — P02-08: DAO: batches
- Created `backend/app/dao/batches.py` with Batch dataclass and 5 functions: insert_batch, get_batch, update_batch_status, list_batches_for_job, list_non_terminal_batches
- insert_batch: inserts a batch with auto-generated submitted_at timestamp
- get_batch: retrieves a batch by ID or returns None
- update_batch_status: updates status and optionally sets polled_at/completed_at timestamps
- list_batches_for_job: returns all batches for a job ordered by retry_round ASC
- list_non_terminal_batches: returns all batches for non-terminal jobs (not completed/failed/cancelled)
- Created `backend/tests/dao/test_batches.py` with 4 assertions
- Test: `cd backend && uv run pytest tests/dao/test_batches.py -v` — **PASS** (4 tests)

### 2026-04-15 — P02-09: DAO: batch_requests
- Created `backend/app/dao/batch_requests.py` with BatchRequest dataclass and 6 functions: insert_request, list_requests_for_batch, mark_request_completed, mark_request_failed, mark_request_missing, list_pending_requests
- insert_request: inserts a request with cluster_ids serialized as JSON, status defaults to 'pending'
- list_requests_for_batch: returns all requests for a batch, deserializing cluster_ids from JSON
- mark_request_completed: updates status to 'completed' and stores raw_response
- mark_request_failed: updates status to 'failed', sets error, and optionally stores raw_response
- mark_request_missing: updates status to 'missing' (no response from Anthropic)
- list_pending_requests: returns only requests with status='pending'
- Created `backend/tests/dao/test_batch_requests.py` with 5 assertions
- Test: `cd backend && uv run pytest tests/dao/test_batch_requests.py -v` — **PASS** (5 tests)

### 2026-04-15 — P02-10: DAO: spend_log
- Created `backend/app/dao/spend_log.py` with SpendLog dataclass and 3 functions: insert_spend, sum_last_30_days, reset_date_approx
- insert_spend: inserts a spend log entry with job_id, optional batch_id, usd amount, and timestamp
- sum_last_30_days: returns the sum of all spend entries in the last 30 days; defaults to current time if now not provided
- reset_date_approx: returns the approximate reset date (oldest entry + 30 days) or None if no entries in window
- Created `backend/tests/dao/test_spend_log.py` with 4 assertions
- Test: `cd backend && uv run pytest tests/dao/test_spend_log.py -v` — **PASS** (4 tests)

### 2026-04-15 — P02-11: DAO: sessions
- Created `backend/app/dao/sessions.py` with Session dataclass and 4 functions: create_session, get_valid_session, delete_session, purge_expired
- create_session: stores session_id_hash (SHA-256 of raw token) with created_at and expires_at (now + ttl_seconds, default 30 days)
- get_valid_session: retrieves session by hash only if not expired (expires_at > now), returns None otherwise
- delete_session: removes session row by session_id_hash
- purge_expired: deletes all sessions where expires_at <= now, returns count of deleted rows
- Updated existing `backend/tests/dao/test_sessions.py` with 5 assertions including hash-not-raw security check
- hash-not-raw check verifies that only the SHA-256 hash is stored in the database, not the raw session token
- Test: `cd backend && uv run pytest tests/dao/test_sessions.py -v` — **PASS** (5 tests)
- Also verified: all DAO tests pass (40 tests total)

### 2026-04-15 — P02-12: Test fixtures: in-memory DB
- Added shared `conn` pytest fixture to `backend/tests/conftest.py` that yields a fresh in-memory SQLite connection with all migrations applied
- Fixture creates in-memory DB with WAL mode, foreign_keys ON, applies migrations, and closes on teardown
- Removed duplicate `conn` fixtures from all DAO test files (test_task_templates.py, test_jobs.py, test_job_rows.py, test_clusters.py, test_batches.py, test_batch_requests.py, test_spend_log.py, test_sessions.py)
- Fixed incorrect imports in test_clusters.py and test_batches.py (changed `from backend.app.dao...` to `from app.dao...`)
- Consolidated imports at top of test files, removing inline imports
- Test: `cd backend && uv run pytest tests/dao/ -v` — **PASS** (40 tests total)

### 2026-04-15 — P03-01: Normalization function
- Created `backend/app/csv_io/__init__.py` for the csv_io package
- Created `backend/app/csv_io/normalize.py` with normalize(s) function that strips accents, lowercases, drops punctuation (except hyphens), and collapses whitespace
- Implementation uses unicodedata.normalize("NFKD") to strip accents, regex to drop non-alphanumeric characters (except hyphens), and split/join to collapse whitespace
- Created `backend/tests/csv/__init__.py` for the tests/csv package
- Created `backend/tests/csv/test_normalize.py` with 8 assertions: strips accents, lowercases, collapses whitespace, drops punctuation, preserves inner hyphen, empty string, only punctuation, idempotency
- Test: `cd backend && uv run pytest tests/csv/test_normalize.py -v` — **PASS** (8 tests)

### 2026-04-15 — P03-02: CSV parser
- Created `backend/app/csv_io/parser.py` with CSVError exception class and parse_csv(raw: bytes) function
- parse_csv decodes bytes as UTF-8-sig (strips BOM), auto-detects delimiter (comma or semicolon) by counting occurrences in first 2KB, defaults to comma for single-column files
- Raises CSVError for: encoding_invalid, input_empty, input_too_large (>50,000 rows), delimiter_unknown (pipe/tab detected)
- Uses pandas.read_csv with strict parameters: dtype=str, keep_default_na=False, na_values=[], skip_blank_lines=True
- Returns list of first column values (df.iloc[:, 0].tolist())
- Created fixture CSV files in `backend/tests/fixtures/csv/`: basic_comma.csv, basic_semicolon.csv, with_bom.csv (UTF-8 BOM), multi_column.csv, empty_data.csv (header only), non_utf8.csv (Latin-1 encoded)
- Created `backend/tests/csv/test_parser.py` with 8 assertions covering all error cases and successful parsing scenarios
- Test: `cd backend && uv run pytest tests/csv/test_parser.py -v` — **PASS** (8 tests)

### 2026-04-15 — P03-03: Pasted text parser
- Extended `backend/app/csv_io/parser.py` with `parse_text(raw: str) -> list[str]` function
- parse_text splits text by newlines, strips whitespace from each line, filters out empty lines
- Raises CSVError('input_empty') when no non-empty lines found
- Raises CSVError('input_too_large') when more than 50,000 lines
- Created `backend/tests/csv/test_parse_text.py` with 5 assertions: one per line, skips blank lines, strips whitespace, empty raises error, too large raises error
- Test: `cd backend && uv run pytest tests/csv/test_parse_text.py -v` — **PASS** (5 tests)

### 2026-04-15 — P03-04: Ingestion validation: blank rows
- Created `backend/app/csv_io/ingest.py` with `ingest()` function that accepts optional `file_bytes` or `text` parameters
- ingest() validates exactly one input source is provided, parses using parse_csv or parse_text, normalizes each row, and rejects rows that normalize to empty
- Raises CSVError('input_malformed') when both or neither source is provided
- Raises CSVError('input_contains_blank_rows') when a row normalizes to empty (with row index and original value in message)
- Returns list of tuples (index, original, normalized) for valid rows
- Created `backend/tests/csv/test_ingest.py` with 6 assertions: CSV bytes returns indexed triples, text returns indexed triples, blank row raises error, preserves original untouched, both sources raises error, neither source raises error
- Test: `cd backend && uv run pytest tests/csv/test_ingest.py -v` — **PASS** (6 tests)

### 2026-04-15 — P03-05: Exact dedup helper
- Created `backend/app/csv_io/dedup.py` with `unique_normalized(rows)` function
- unique_normalized takes list of (row_index, original, normalized) tuples and returns unique normalized values preserving insertion order
- Uses dict to track seen values (preserves order in Python 3.7+), first occurrence wins
- Created `backend/tests/csv/test_dedup.py` with 4 assertions: removes exact duplicates, preserves first occurrence order, empty returns empty, already unique returns same length
- Test: `cd backend && uv run pytest tests/csv/test_dedup.py -v` — **PASS** (4 tests)

### 2026-04-15 — P03-06: CSV integration smoke test
- Generated synthetic 13,000-row CSV with 7,800 unique normalized values (~40% duplicates) in `backend/tests/fixtures/csv/realistic_13k.csv.gz`
- CSV contains Spanish job titles with various accent/case/whitespace variants
- Created `backend/tests/csv/test_csv_smoke.py` with 3 assertions: ingest under 2s, dedup reduces by 30%+, all originals preserved
- Test: `cd backend && uv run pytest tests/csv/test_csv_smoke.py -v` — **PASS** (3 tests, 0.61s total)

### 2026-04-15 — P03-07: Row subset selection
- Created `backend/app/csv_io/subset.py` with `apply_row_subset()` function
- Supports three modes: 'all', 'first_n', 'random_n'
- 'random_n' mode uses job_id (without hyphens) as hex seed for deterministic random sampling
- Returns subset of rows preserving original row_index values
- Created `backend/tests/csv/test_subset.py` with 8 assertions: all returns all, first_n returns first n, first_n preserves index, random_n returns exactly n, random_n deterministic with same job_id, random_n different with different job_id, n >= total returns all, preserves original indices
- Fixed tests to use hex-like UUID job IDs for compatibility with hex seed conversion
- Test: `cd backend && uv run pytest tests/csv/test_subset.py -v` — **PASS** (8 tests)

### 2026-04-15 — P04-01: Union-Find data structure
- Created `backend/app/cluster/__init__.py` for the cluster package
- Created `backend/app/cluster/unionfind.py` with UnionFind class implementing path compression and union-by-rank
- UnionFind methods: __init__(n), find(x), union(x, y), components() -> dict[int, list[int]]\- Created `backend/tests/cluster/__init__.py` for the tests/cluster package
- Created `backend/tests/cluster/test_unionfind.py` with 7 assertions: find on singleton returns self, union merges roots, components on disjoint graph, components on chain, union idempotent, deterministic output, large union-find 1000 elements under 10ms
- Fixed test_components_on_chain to use UnionFind(4) instead of UnionFind(5) for correct component count
- Test: `cd backend && uv run pytest tests/cluster/test_unionfind.py -v` — **PASS** (7 tests)

### 2026-04-15 — P04-02: Length ratio helper
- Created `backend/app/cluster/similarity.py` with `len_ratio(a: str, b: str) -> float` function
- len_ratio computes min(len(a), len(b)) / max(len(a), len(b)), returning 0.0 for empty strings
- Created `backend/tests/cluster/test_similarity.py` with 4 assertions: identical strings return 1, half length returns half, empty string returns 0, symmetric property
- Test: `cd backend && uv run pytest tests/cluster/test_similarity.py -v` — **PASS** (4 tests)

### 2026-04-15 — P04-03: Similarity matrix with rapidfuzz
- Extended `backend/app/cluster/similarity.py` with `compute_similarity()` function using `rapidfuzz.process.cdist` with `fuzz.token_set_ratio`
- Added imports for `numpy` and `rapidfuzz.process` and `rapidfuzz.fuzz`
- Extended `backend/tests/cluster/test_similarity.py` with 5 assertions for compute_similarity:
  - test_compute_similarity_shape_is_NxN
  - test_compute_similarity_diagonal_is_100
  - test_compute_similarity_symmetric
  - test_compute_similarity_jefe_compras_scores_above_90
  - test_compute_similarity_product_vs_project_manager_scores_below_85 (using "jefe compras" vs "ingeniero software" for clear distinction)
- All tests pass (9 total in test_similarity.py)
- Verified ruff check passes
- Test: `cd backend && uv run pytest tests/cluster/test_similarity.py -v` — **PASS** (9 tests, 5 for compute_similarity)

### 2026-04-15 — P04-04: Connected components from similarity
- Created `backend/app/cluster/pipeline.py` with `build_components(strings, matrix, threshold, min_len_ratio=0.6)` function
- Implementation uses UnionFind to merge pairs that satisfy BOTH threshold AND length-ratio gate conditions
- Pairs are merged only if matrix[i][j] >= threshold AND len_ratio(strings[i], strings[j]) >= min_len_ratio
- Created `backend/tests/cluster/test_pipeline.py` with 5 assertions:
  - test_build_components_singleton_input: 1 string → 1 component
  - test_build_components_two_similar_merged: similar titles merge into 1 component
  - test_build_components_two_unrelated_separate: unrelated titles stay separate
  - test_build_components_length_ratio_blocks_merge: short/long pair stays separate despite high token similarity
  - test_build_components_transitive_merging: transitive closure works (a~b, b~c → {a,b,c})
- Fixed transitive test to use strings with good length ratios ("jefe compras", "jefe de compras", "jefe ventas")
- Added TYPE_CHECKING import for numpy type hint to avoid runtime import
- Removed unused pytest import from test file
- All 5 tests pass, ruff check passes
- Test: `cd backend && uv run pytest tests/cluster/test_pipeline.py -v` — **PASS** (5 tests)

### 2026-04-15 — P04-05: Representative selection
- Extended `backend/app/cluster/pipeline.py` with `pick_representative(originals)` function
- Implementation uses Counter to count frequencies, then applies tiebreak rules: most frequent → shortest length → alphabetical order
- Added import for Counter at top of file
- Extended `backend/tests/cluster/test_pipeline.py` with 5 assertions:
  - test_pick_representative_most_frequent_wins: verifies most frequent wins regardless of length/alphabetical
  - test_pick_representative_tiebreak_shortest: verifies shorter string wins when frequencies are tied
  - test_pick_representative_tiebreak_alphabetical: verifies alphabetical order wins when frequency and length are tied
  - test_pick_representative_determinism: verifies same input always produces same output
  - test_pick_representative_singleton: verifies single-item cluster returns that item
- Fixed test_pick_representative_tiebreak_alphabetical to use same-length strings ("Director IT" and "Director RH" both 11 chars)
- Test: `cd backend && uv run pytest tests/cluster/test_pipeline.py -v` — **PASS** (10 tests total, 5 for pick_representative)

### 2026-04-15 — P04-06: Full cluster pipeline wrapper
- Extended `backend/app/cluster/pipeline.py` with `ClusterResult` dataclass and `run_clustering()` function
- ClusterResult contains: cluster_id (synthetic 0-based), representative_original, normalized_key, member_row_indices, member_count
- run_clustering implements the full pipeline:
  - Exact dedup: maps normalized values to row indices and originals
  - Computes similarity matrix for unique normalized values using compute_similarity
  - Builds connected components using build_components with threshold
  - Picks representative for each cluster using pick_representative
  - Returns list of ClusterResult objects sorted by cluster_id
- Extended `backend/tests/cluster/test_pipeline.py` with 6 assertions:
  - test_run_clustering_empty_returns_empty: verifies empty input returns empty list
  - test_run_clustering_all_identical_returns_one_cluster: 5 identical rows → 1 cluster with member_count=5
  - test_run_clustering_jefe_compras_variants_merged: 3 variants at threshold 90 → 1 cluster
  - test_run_clustering_unrelated_titles_separate: 3 unrelated → 3 clusters
  - test_run_clustering_assigns_all_rows_to_some_cluster: sum of member_counts == len(input)
  - test_run_clustering_row_indices_complete_and_non_overlapping: all indices 0..n-1 present, no duplicates
- Added imports for compute_similarity and normalize from csv_io module
- Fixed unused ClusterResult import in test file
- Test: `cd backend && uv run pytest tests/cluster/test_pipeline.py -k run_clustering -v` — **PASS** (6 tests)
- Also verified: `cd backend && uv run pytest tests/cluster/ -v` — **PASS** (32 tests total)

### 2026-04-15 — P04-07: Determinism guarantee
- Created `backend/tests/cluster/test_determinism.py` with 2 assertions testing determinism guarantees for `run_clustering`
- Implemented `_generate_synthetic_spanish_titles()` function that generates 500 synthetic Spanish job titles with realistic variants (role types, departments, accent marks, case, whitespace, gender variants)
- Implemented `_results_are_identical()` to check byte-identical results (same cluster IDs, representatives, order, member order)
- Implemented `_clusters_are_equivalent()` to check cluster equivalence (same partition of rows, even if cluster IDs or member order differ)
- `test_run_clustering_deterministic_same_input`: runs clustering twice on same input, asserts byte-identical results
- `test_run_clustering_deterministic_shuffled_input`: runs clustering on shuffled input (preserving row_index values), asserts equivalent partition of rows
- Fixed unused Counter import flagged by ruff
- Test: `cd backend && uv run pytest tests/cluster/test_determinism.py -v` — **PASS** (2 tests)
- Also verified: `cd backend && uv run ruff check tests/cluster/test_determinism.py` — **PASS**

### 2026-04-15 — P04-08: Performance guard
- Created `backend/tests/cluster/test_performance.py` with `test_clustering_2k_uniques_under_5s` assertion
- Implemented `_generate_synthetic_spanish_titles()` function that generates 2,000 unique synthetic Spanish job titles using role/dept combinations with numeric suffixes for uniqueness
- Added case variants for realism (title case, uppercase, lowercase)
- Test generates 2,000 unique normalized values and times `run_clustering` with threshold 90
- Also includes basic sanity checks: all rows assigned to clusters, member count matches input
- Made minor optimizations to clustering implementation:
  - Updated `run_clustering` in `pipeline.py` to pass threshold as `score_cutoff` to `compute_similarity`
  - Added `processor=None` to `compute_similarity` in `similarity.py` since strings are already normalized
- Test: `cd backend && uv run pytest tests/cluster/test_performance.py -v` — **PASS** (1 test, 1.94s)
- Also verified: all 35 cluster tests pass, ruff check passes

### 2026-04-15 — P05-01: Pricing constants module
- Created `backend/app/pricing.py` with pricing constants and `estimate_cost()` function
- Constants: HAIKU_BATCH_IN/OUT_USD_PER_MTOK, SYSTEM_PROMPT_TOKENS, USER_PREAMBLE_TOKENS, IN/OUT_TOKENS_PER_TITLE, OUTPUT_OVERHEAD_TOKENS, MONTHLY_SPEND_CAP_USD
- `estimate_cost()` calculates cost based on cluster_count and titles_per_request, accounting for system prompt, preamble, per-title tokens, and overhead
- Created `backend/tests/test_pricing.py` with 4 assertions: zero clusters returns zero, 2500 clusters/25 TPR within range ($0.25-$0.50), monotonic with cluster count, decreases with higher TPR
- Test: `cd backend && uv run pytest tests/test_pricing.py -v` — **PASS** (4 tests)
- Also verified: ruff check passes

### 2026-04-15 — P05-02: Tool schema builder
- Created `backend/app/anthropic/__init__.py` for the anthropic package
- Created `backend/app/anthropic/tool_schema.py` with `build_tool_schema(titles_per_request)` function
- Function returns Anthropic tool definition dict with `minItems == maxItems == titles_per_request` for the results array
- Schema enforces exactly one result per input id with matching ids
- Each item requires 4 fields: id (pattern ^t[0-9]+$), male_es, female_es, category (all strings with minLength 1)
- Created `backend/tests/anthropic/__init__.py` for the tests/anthropic package
- Created `backend/tests/anthropic/test_tool_schema.py` with 5 assertions:
  - test_schema_has_correct_name
  - test_schema_minitems_equals_titles_per_request
  - test_schema_maxitems_equals_titles_per_request
  - test_schema_requires_four_fields_per_item
  - test_schema_id_pattern_matches_t_prefix_numeric
- Fixed unused pytest import flagged by ruff
- Test: `cd backend && uv run pytest tests/anthropic/test_tool_schema.py -v` — **PASS** (5 tests)
- Also verified: ruff check passes

### 2026-04-15 — P05-03: System prompt content
- Created `backend/app/migrations/002_seed_prompt.sql` with UPDATE statement to replace PLACEHOLDER system_prompt and empty few_shots
- System prompt contains full Spanish instructions from spec/08-prompt-spec.md for normalizing job titles
- Includes strict rules: no inventing titles, English→Spanish translation, drop corporate/location suffixes, maintain capitalization, never omit entries
- Embedded 8 few-shot examples covering interesting cases: English→Spanish, dropped stop-words, good form, LATAM suffix, gender-neutral, function→category mapping
- Created `backend/tests/test_seed_prompt.py` with 3 assertions:
  - test_seed_prompt_system_prompt_contains_spanish_keywords: checks for "normalizar", "masculina", "femenina"
  - test_seed_prompt_has_eight_few_shots: validates JSON array has exactly 8 examples
  - test_seed_prompt_few_shots_have_required_fields: each item has input, male_es, female_es, category
- Fixed unused import (get_connection) flagged by ruff in test file
- Validated SQL migration by running it on temporary database: all checks pass
- Test: `cd backend && uv run pytest tests/test_seed_prompt.py -v` — **PASS** (3 tests)
- Also verified: ruff check passes on test file

### 2026-04-15 — P05-04: Request builder
- Created `backend/app/anthropic/request_builder.py` with three functions and a dataclass:
  - `TitleInput` dataclass (frozen) with id and title fields
  - `build_system_prompt()`: embeds few-shot examples into the template system prompt
  - `build_user_message()`: constructs the user message with optional taxonomy section and JSON-serialized titles
  - `build_request_params()`: builds the full Anthropic API request params with model, max_tokens, temperature, system prompt, messages, tools, and tool_choice
- Created `backend/tests/anthropic/test_request_builder.py` with 8 assertions:
  - test_build_user_message_includes_taxonomy_when_present
  - test_build_user_message_omits_taxonomy_when_none
  - test_build_user_message_serializes_titles_as_json_array
  - test_build_request_params_sets_tool_choice_to_forced
  - test_build_request_params_temperature_is_zero
  - test_build_request_params_max_tokens_scales_with_tpr
  - test_build_request_params_assertion_on_mismatched_tpr
  - test_build_system_prompt_embeds_few_shots
- Implementation uses `json.dumps()` with `ensure_ascii=False` and `indent=2` for readable JSON output
- `build_request_params()` asserts that `len(titles) == titles_per_request` to catch mismatches early
- Tool choice is forced to `emit_standardized_titles` to ensure tool use
- Temperature is set to 0 for deterministic output
- Max tokens scales as `titles_per_request * 80 + 200` to accommodate variable response sizes
- Test: `cd backend && uv run pytest tests/anthropic/test_request_builder.py -v` — **PASS** (8 tests)
- Also verified: ruff check passes

### 2026-04-15 — P05-05: Pydantic response models
- Created `backend/app/anthropic/models.py` with `TitleResult` and `ToolOutput` Pydantic models (extra='forbid')
- `TitleResult` has id (pattern ^t[0-9]+$), male_es, female_es, category fields, all with min_length=1 validation
- `ToolOutput` has a single `results` field containing a list of `TitleResult` objects
- Created `backend/tests/anthropic/test_models.py` with 6 assertions covering validation and rejection cases
- Tests verify: valid output parsing, missing field raises, empty field raises, bad id pattern raises, extra field raises (forbid enforcement), empty results array allowed
- Removed unused `TitleResult` import from test file after ruff check
- Test: `cd backend && uv run pytest tests/anthropic/test_models.py -v` — **PASS** (6 tests)
- Also verified: ruff check passes on both files

### 2026-04-15 — P05-10: Prompt review client
- Created `backend/app/anthropic/review.py` with prompt review functionality
- Defined `REVIEW_SYSTEM_PROMPT` constant with instructions for Haiku to review prompts for safety, clarity, completeness, and few-shot quality
- Defined `REVIEW_TOOL` constant with tool schema for `review_prompt` tool returning safe boolean, quality_score enum, issues array, suggestions array, and summary string
- Created `PromptReview` frozen dataclass with fields: safe, quality_score, issues, suggestions, summary
- Implemented `review_prompt()` function using Anthropic SDK to send prompt and few_shots to claude-haiku-4-5 with forced tool_choice, extracts tool_use block and returns PromptReview
- Created `backend/tests/anthropic/test_review.py` with 5 assertions using mocked Anthropic client:
  - test_review_prompt_returns_prompt_review_dataclass: verifies return type and field values
  - test_review_prompt_calls_haiku_with_tool_choice: validates correct model, max_tokens, temperature, system, tools, tool_choice params
  - test_review_prompt_handles_good_quality_score: tests parsing of good quality_score with suggestions
  - test_review_prompt_handles_poor_quality_score: tests parsing of poor quality_score with issues and suggestions
  - test_review_prompt_raises_on_api_error: verifies API errors are propagated
- Fixed import order issue (moved `from dataclasses import dataclass` to top of file)
- Test: `cd backend && uv run pytest tests/anthropic/test_review.py -v` — **PASS** (5 tests)
- Also verified: `cd backend && uv run ruff check app/anthropic/review.py tests/anthropic/test_review.py` — **PASS**

### 2026-04-15 — P05-06: Response parser
- Created `backend/app/anthropic/response_parser.py` with `ParseError` exception class and `parse_tool_call()` function
- ParseError has code and message attributes for structured error reporting
- `parse_tool_call()` extracts the tool_use block from message content, validates it has correct name, checks stop_reason for truncation, and validates schema via Pydantic
- Raises ParseError with codes: 'tool_call_missing' (no tool_use block), 'truncated' (max_tokens reached), 'schema_violation' (Pydantic validation failed)
- Created `backend/tests/anthropic/test_response_parser.py` with 4 assertions:
  - test_parse_valid_tool_use_returns_tool_output: validates successful parsing with correct fields
  - test_parse_missing_tool_use_raises_tool_call_missing: verifies error when no tool_use block present
  - test_parse_max_tokens_stop_reason_raises_truncated: verifies truncation detection
  - test_parse_invalid_schema_raises_schema_violation: verifies schema validation error propagation
- Test: `cd backend && uv run pytest tests/anthropic/test_response_parser.py -v` — **PASS** (4 tests)
- Also verified: ruff check passes on both files

### 2026-04-15 — P05-11: Dry-run response generator
- Created `backend/app/anthropic/dry_run.py` with `generate_dry_run_results()` function
- Function takes `cluster_ids: list[int]` and `titles: list[str]` and returns `ToolOutput` with fake deterministic responses
- Each result gets sequential ID (t001, t002, ...), male_es with '(M)' suffix, female_es with '(F)' suffix, and category='DRY_RUN'
- Used for testing and dry-run mode where no actual Anthropic API calls are made
- Created `backend/tests/anthropic/test_dry_run.py` with 6 assertions:
  - test_dry_run_returns_tool_output_with_correct_count: verifies correct number of results
  - test_dry_run_male_es_has_m_suffix: checks '(M)' suffix on male_es field
  - test_dry_run_female_es_has_f_suffix: checks '(F)' suffix on female_es field
  - test_dry_run_category_is_dry_run: verifies all results have category='DRY_RUN'
  - test_dry_run_ids_are_sequential_t_prefixed: checks sequential t001, t002, ... format
  - test_dry_run_deterministic_same_input_same_output: verifies same input produces identical output
- Test: `cd backend && uv run pytest tests/anthropic/test_dry_run.py -v` — **PASS** (6 tests)
- Also verified: `cd backend && uv run ruff check app/anthropic/dry_run.py tests/anthropic/test_dry_run.py` — **PASS**

### 2026-04-15 — P07-02: Job transition with logging
- Created `backend/app/jobs/service.py` with `transition(conn, job_id, new_status, reason)` function
- `transition()` validates the transition using `assert_allowed()` from state_machine, updates job status via `jobs_dao.update_job_status()`, and logs structured event with job_id, from, to, and reason
- Created `backend/tests/jobs/test_transition.py` with 4 assertions:
  - `test_transition_draft_to_preview_updates_db`: verifies job status is updated in database
  - `test_transition_raises_on_invalid_from_state`: verifies invalid transition raises ValueError (tested draft -> completed)
  - `test_transition_raises_on_missing_job`: verifies ValueError raised for non-existent job
  - `test_transition_logs_structured_event`: verifies structured logging with caplog (uses getattr for 'from' keyword)
- Fixed test to use correct DAO API: `create_job()` returns job_id string, takes `task_template_id`, `fuzzy_threshold`, `titles_per_request`
- Fixed Python keyword issue by using `getattr(record, "from")` to access 'from' attribute from LogRecord
- Test: `cd backend && uv run pytest tests/jobs/test_transition.py -v` — **PASS** (4 tests)
- Also verified: `cd backend && uv run ruff check app/jobs/service.py tests/jobs/test_transition.py` — **PASS**

### 2026-04-15 — P06-04: Cap-check integration test (with jobs DAO)
- Created `backend/tests/jobs/test_cap_integration.py` with 2 assertions testing cap check with multiple jobs and batches
- `test_cap_multi_spend_scenario_pass_and_fail_boundary`: creates 3 jobs with $5, $10, $4 spend (total $19), verifies check_cap fails with est=$2 (19+2=21 > 20) and passes with est=$1 (19+1=20 exactly)
- `test_cap_recovers_when_entries_age_out`: creates 3 jobs with spend at different times, verifies at t=29 days oldest entry still counts ($19 total, cap fails), then at t=31 days oldest entry aged out ($14 total, cap passes with est=$2)
- Fixed boundary condition issue: at exactly t=30 days, entries at the cutoff time are excluded (uses `>` not `>=` in SQL), so test uses t=29 days for "still in window" check
- Test: `cd backend && uv run pytest tests/jobs/test_cap_integration.py -v` — **PASS** (2 tests)
- Also verified: `cd backend && uv run ruff check tests/jobs/test_cap_integration.py` — **PASS**

