# FinAlly - single image, single port.
# Stage 1 builds the static frontend, stage 2 runs FastAPI and serves it.
# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: build the Next.js static export
# ---------------------------------------------------------------------------
FROM node:20-slim AS frontend

WORKDIR /build

# Manifests first so a source-only change does not reinstall node_modules.
# Both sources are in one COPY: package.json always matches, so the optional
# lockfile glob matching nothing is not an error.
COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY frontend/ ./
# next.config sets output: 'export', so this produces ./out
RUN npm run build

# ---------------------------------------------------------------------------
# uv, pinned to the version that produced backend/uv.lock. Kept as its own
# stage so it can be bind-mounted for the sync and never committed to a layer
# in the runtime image - the binaries are ~64MB and unused at runtime.
# ---------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:0.11.31 AS uv

# ---------------------------------------------------------------------------
# Stage 2: FastAPI runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PATH="/app/.venv/bin:$PATH" \
    DB_PATH=/app/db/finally.db

# Dependency layer: manifests only, so it is reused until they change.
# The cache mount keeps uv's wheel downloads out of the image; UV_LINK_MODE=copy
# means the venv is self-contained and does not reference the cache.
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=from=uv,source=/uv,target=/usr/local/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Application code. --no-install-project keeps this out of a wheel build;
# PYTHONPATH=/app makes the `app` package importable as-is, and main.py
# resolves ./static as <this file>/../.. /static, which is /app/static.
COPY backend/app ./app

# Static frontend export.
COPY --from=frontend /build/out ./static

# Exists so the app still runs when no volume is mounted at /app/db.
RUN mkdir -p /app/db

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
