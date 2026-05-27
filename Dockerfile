# Stage 1: frontend build
FROM node:22-alpine AS fe-build
WORKDIR /fe
RUN npm install -g pnpm@10 --quiet
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

# Stage 2: Python runtime
FROM python:3.12-slim AS runtime
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
ENV UV_LINK_MODE=copy
RUN uv sync --frozen --no-dev
COPY backend/ ./
COPY --from=fe-build /fe/dist /app/static
ENV STATIC_DIR=/app/static
EXPOSE 8080
CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
