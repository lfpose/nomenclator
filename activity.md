# Nomenclator — Activity Log

## Current Status
**Last Updated:** 2026-04-15
**Tasks Completed:** 19
**Current Task:** P03-01

---

## Session Log

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
