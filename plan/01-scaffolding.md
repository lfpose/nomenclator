# 01 — Scaffolding

Repo layout, dependencies, and the minimum skeletons that boot. No business logic. By the end of this phase: `pytest` runs (zero tests) and `pnpm dev` serves a blank page at `/`, `/about`, `/docs`.

---

### P01-01 — Directory structure

**Deps:** —
**Files:** (creates directories + empty `__init__.py` files and placeholder `.gitkeep`s matching `plan/00-index.md` "Canonical directory layout")
**Goal:** Create every directory in the canonical layout with placeholder files so imports won't fail later.

**Implementation:**
- Create `backend/app/`, `backend/app/migrations/`, `backend/app/dao/`, `backend/app/csv_io/`, `backend/app/cluster/`, `backend/app/anthropic/`, `backend/app/jobs/`, `backend/app/worker/`, `backend/app/auth/`, `backend/app/api/`.
- Create matching `backend/tests/` subdirectories.
- Create `frontend/src/`, `frontend/src/routes/`, `frontend/src/components/`, `frontend/src/hooks/`, `frontend/src/lib/`, `frontend/src/styles/`, `frontend/tests/`.
- Add empty `__init__.py` to every Python package directory.
- Add `.gitkeep` where no real files exist yet.

**Test:** `find backend frontend -type d | sort > /tmp/dirs.txt && diff /tmp/dirs.txt plan/fixtures/expected-dirs.txt`

Required assertions:
- The `find` output matches the expected layout exactly.

**Done when:**
- [ ] All directories in `plan/00-index.md` exist.
- [ ] `python -c "import backend.app"` succeeds (no import error).

---

### P01-02 — Python project setup

**Deps:** P01-01
**Files:** `backend/pyproject.toml`, `backend/uv.lock` (generated), `backend/.python-version`
**Goal:** Set up Python project with `uv`, pinned 3.12, all v1 dependencies declared.

**Implementation:**
```toml
# backend/pyproject.toml
[project]
name = "nomenclator"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.9",
    "pydantic-settings>=2.5",
    "httpx>=0.27",
    "rapidfuzz>=3.10",
    "pandas>=2.2",
    "numpy>=2.1",
    "python-multipart>=0.0.12",
    "argon2-cffi>=23.1",
    "anthropic>=0.39",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5.0",
    "ruff>=0.7",
    "pytest-httpx>=0.33",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
line-length = 100
target-version = "py312"
```

- Write `backend/.python-version` containing `3.12`.
- Run `uv sync --extra dev` once to generate the lockfile.

**Test:** `cd backend && uv run pytest --collect-only`

Required assertions:
- Exit code 0.
- Output contains `collected 0 items`.

**Done when:**
- [ ] `uv sync` succeeds without warnings.
- [ ] `uv run pytest --collect-only` exits 0.
- [ ] `uv run ruff check .` exits 0.

---

### P01-03 — FastAPI hello-world skeleton

**Deps:** P01-02
**Files:** `backend/app/main.py`, `backend/app/settings.py`, `backend/tests/test_smoke.py`
**Goal:** A FastAPI app that boots and returns 200 on `GET /health` with a stub body.

**Implementation:**
```python
# backend/app/settings.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    version: str = "0.1.0"
    database_path: str = "/tmp/nomenclator.db"
    anthropic_api_key: str = "test"
    auth_password_hash: str = ""
    monthly_spend_cap_usd: float = 20.0

    class Config:
        env_prefix = ""
        env_file = ".env"

settings = Settings()
```

```python
# backend/app/main.py
from fastapi import FastAPI
from .settings import settings

def create_app() -> FastAPI:
    app = FastAPI(title="Nomenclator", version=settings.version)

    @app.get("/health")
    def health():
        return {"ok": True, "version": settings.version}

    return app

app = create_app()
```

```python
# backend/tests/test_smoke.py
from fastapi.testclient import TestClient
from app.main import create_app

def test_health_returns_200():
    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True

def test_health_reports_version():
    client = TestClient(create_app())
    r = client.get("/health")
    assert "version" in r.json()
```

**Test:** `cd backend && uv run pytest tests/test_smoke.py -v`

Required assertions:
- `test_health_returns_200`
- `test_health_reports_version`

**Done when:**
- [ ] Both tests pass.
- [ ] `uv run uvicorn app.main:app` starts without errors.

---

### P01-04 — Frontend project skeleton

**Deps:** P01-01
**Files:** `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/index.html`, `frontend/src/main.tsx`
**Goal:** Vite + React + TypeScript project that builds.

**Implementation:**
- Run `pnpm create vite frontend --template react-ts` equivalent, adjusted to existing directory.
- Add dependencies: `react`, `react-dom`, `@tanstack/react-router`, `@fontsource-variable/inter`, `@fontsource-variable/fraunces`, `@fontsource/jetbrains-mono`, `mermaid`, `tailwindcss`, `@tailwindcss/vite`.
- Dev deps: `vite`, `typescript`, `@types/react`, `@types/react-dom`, `@vitejs/plugin-react`, `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom`, `prettier`.
- `vite.config.ts` exports a config with `plugins: [tailwindcss(), react()]`, `server.port: 5173`.
- `tsconfig.json` with `strict: true`, `jsx: "react-jsx"`.
- `src/main.tsx` mounts a minimal `<div>Nomenclator</div>` React root.
- Run `npx shadcn@latest init` with neutral theme; configure `components.json` (output dir `src/components/ui`, aliases matching the tsconfig paths).
- Create `frontend/src/styles/globals.css` importing Tailwind and the shadcn CSS variables for light/dark modes (monochrome palette from `spec/11-design-system.md`).

**Test:** `cd frontend && pnpm build && pnpm test --run`

Required assertions:
- `pnpm build` exits 0 and produces `dist/index.html`.
- `pnpm test --run` exits 0 (no tests yet, that's fine).

**Done when:**
- [ ] `pnpm build` succeeds.
- [ ] `pnpm tsc --noEmit` exits 0.
- [ ] `dist/index.html` exists.

---

### P01-05 — TanStack Router with 3 empty routes

**Deps:** P01-04
**Files:** `frontend/src/main.tsx` (replaced), `frontend/src/routes/__root.tsx`, `frontend/src/routes/index.tsx`, `frontend/src/routes/about.tsx`, `frontend/src/routes/docs.tsx`, `frontend/src/router.ts`
**Goal:** Three routes (`/`, `/about`, `/docs`) rendering distinct placeholder text.

**Implementation:**
- Use TanStack Router code-based routing (not file-based, simpler for v1).
- `__root.tsx` exports a root route with a `<Outlet />` and three `<Link>` elements.
- Each of the three leaf routes renders `<h1>Tool / About / Docs</h1>`.
- `router.ts` assembles the `createRouter` instance.
- `main.tsx` wraps `<RouterProvider router={router} />`.

**Test:** `cd frontend && pnpm test --run tests/router.test.tsx`

Required assertions (create `frontend/tests/router.test.tsx`):
- `test("renders Tool page at /", ...)` — asserts `/Tool/` text present.
- `test("renders About page at /about", ...)` — asserts `/About/` text present.
- `test("renders Docs page at /docs", ...)` — asserts `/Docs/` text present.

**Done when:**
- [ ] All 3 routes render correct placeholder text in test.
- [ ] `pnpm build` still succeeds.

---

### P01-06 — Combined multi-stage Dockerfile

**Deps:** P01-02, P01-04
**Files:** `Dockerfile`, `.dockerignore`
**Goal:** A single Dockerfile that builds frontend static assets, then copies them into the Python runtime image alongside the FastAPI app.

**Implementation:**
```dockerfile
# Stage 1: frontend build
FROM node:20-alpine AS fe-build
WORKDIR /fe
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

# Stage 2: Python runtime
FROM python:3.12-slim AS runtime
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/ ./
COPY --from=fe-build /fe/dist /app/static
ENV STATIC_DIR=/app/static
EXPOSE 8080
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

- `.dockerignore` excludes `node_modules`, `__pycache__`, `*.pyc`, `.venv`, `.git`.

**Test:** `docker build -t nomenclator:test . && docker run --rm -d -p 8080:8080 --name nom-test nomenclator:test && sleep 3 && curl -sf http://localhost:8080/health && docker stop nom-test`

Required assertions:
- Docker build exits 0.
- `curl /health` returns `{"ok": true, ...}`.

**Done when:**
- [ ] Docker image builds in < 5 minutes on a clean cache.
- [ ] Running container serves `/health`.

---

### P01-07 — fly.toml with persistent volume

**Deps:** P01-06
**Files:** `fly.toml`
**Goal:** Fly.io configuration targeting a single machine with a persistent volume mounted at `/data`.

**Implementation:**
```toml
app = "nomenclator"
primary_region = "scl"

[build]
dockerfile = "Dockerfile"

[env]
DATABASE_PATH = "/data/nomenclator.db"
STATIC_DIR = "/app/static"

[[mounts]]
source = "nomenclator_data"
destination = "/data"

[http_service]
internal_port = 8080
force_https = true
auto_stop_machines = false
auto_start_machines = true
min_machines_running = 1

[[http_service.checks]]
interval = "30s"
timeout = "5s"
grace_period = "10s"
method = "GET"
path = "/health"
```

**Test:** `fly config validate`

Required assertions:
- Command exits 0.

**Done when:**
- [ ] `fly config validate` passes.
- [ ] File is committed.

---

### P01-08 — Dev scripts (Makefile)

**Deps:** P01-02, P01-04
**Files:** `Makefile`
**Goal:** Single-command shortcuts for common dev tasks.

**Implementation:**
```makefile
.PHONY: install test lint format dev-backend dev-frontend build

install:
	cd backend && uv sync --extra dev
	cd frontend && pnpm install

test:
	cd backend && uv run pytest
	cd frontend && pnpm test --run

lint:
	cd backend && uv run ruff check .
	cd frontend && pnpm tsc --noEmit

format:
	cd backend && uv run ruff format .
	cd frontend && pnpm prettier --write src/

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8080

dev-frontend:
	cd frontend && pnpm dev

build:
	cd frontend && pnpm build
	docker build -t nomenclator:dev .
```

**Test:** `make lint && make test`

Required assertions:
- Both commands exit 0.

**Done when:**
- [ ] `make install` bootstraps from a clean clone.
- [ ] `make test` runs the 2 smoke tests from P01-03 and the 3 router tests from P01-05.

---

### P01-09 — shadcn/ui base components

**Deps:** P01-04
**Files:** `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/input.tsx`, `frontend/src/components/ui/textarea.tsx`, `frontend/src/components/ui/card.tsx`, `frontend/src/components/ui/badge.tsx`, `frontend/src/components/ui/dialog.tsx`, `frontend/src/components/ui/switch.tsx`, `frontend/src/components/ui/tooltip.tsx`, `frontend/src/components/ui/select.tsx`, `frontend/src/components/ui/slider.tsx`, `frontend/src/components/ui/collapsible.tsx`, `frontend/src/components/ui/table.tsx`, `frontend/src/components/ui/label.tsx`, `frontend/src/components/ui/separator.tsx`, `frontend/src/components/ui/scroll-area.tsx`, `frontend/src/components/ui/toaster.tsx`, `frontend/tests/shadcn-smoke.test.tsx`
**Goal:** Install all shadcn/ui components needed for v1 via the CLI. Verify they render.

**Implementation:**
Run for each component:
```bash
npx shadcn@latest add button input textarea card badge dialog switch tooltip select slider collapsible table label separator scroll-area
```
Install `sonner` for toasts: `pnpm add sonner`.

**Test:** `cd frontend && pnpm test --run tests/shadcn-smoke.test.tsx`

Required assertions:
- `test("Button renders with children", ...)`
- `test("Input renders with placeholder", ...)`
- `test("Switch toggles checked state", ...)`
- `test("Badge renders with variant", ...)`
- `test("Tooltip shows content on hover", ...)`

**Done when:**
- [ ] All 5 tests pass.
- [ ] `pnpm build` succeeds with no TS errors.
- [ ] `frontend/src/components/ui/` contains all listed component files.
