# nomenclator

Full-stack AI-powered naming/clustering tool. FastAPI backend + React frontend.

## Stack

- **Backend**: Python, FastAPI, `uv`, SQLite (via `db.py`), Anthropic SDK, background worker (`worker/poller.py`)
- **Frontend**: React, TypeScript, Vite, TanStack Router, `pnpm`, Tailwind + shadcn/ui

## Commands

```bash
make install        # install all deps (backend + frontend)
make test           # run all tests
make lint           # ruff + tsc typecheck
make format         # ruff format + prettier
make dev-backend    # uvicorn on :8080 (hot reload)
make dev-frontend   # vite dev server
make build          # frontend build + docker image
```

## Key paths

| Area | Path |
|------|------|
| API routes | `backend/app/api/` |
| Background worker | `backend/app/worker/` |
| Anthropic integration | `backend/app/anthropic/` |
| DB / migrations | `backend/app/db.py`, `backend/app/migrations/` |
| Frontend pages | `frontend/src/routes/` |
| Frontend components | `frontend/src/components/` |

## Dev notes

- Backend tests: `cd backend && uv run pytest`
- Frontend tests: `cd frontend && pnpm test --run`
- Linting: `ruff check` / `ruff format` — no manual `# noqa` unless necessary
- Deployed to Fly.io (`fly.toml`) — see `DEPLOYMENT.md` for full details

## Deploy

```bash
~/.fly/bin/flyctl deploy --app nomenclator
```

Secrets are managed via `flyctl secrets set KEY=value` — never commit them. See `DEPLOYMENT.md`.
