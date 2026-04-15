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
