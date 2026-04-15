# Nomenclator — Activity Log

## Current Status
**Last Updated:** 2026-04-15
**Tasks Completed:** 2
**Current Task:** P01-03

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
