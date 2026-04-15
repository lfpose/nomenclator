# Nomenclator — Activity Log

## Current Status
**Last Updated:** 2026-04-15
**Tasks Completed:** 14
**Current Task:** P02-07

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
