# =============================================================================
#  Talk to AI — Multi-stage Dockerfile
#  Single production image containing both the built frontend & the FastAPI
#  backend. The frontend static files are served directly by FastAPI.
# =============================================================================

# ---------------------------------------------------------------------------
#  Stage 1 — Build the React frontend into a dist/ folder
# ---------------------------------------------------------------------------
FROM docker.io/library/node:24-alpine AS frontend-builder

WORKDIR /build/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --omit=dev

COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
#  Stage 2 — Install production Python dependencies into a portable location
# ---------------------------------------------------------------------------
FROM docker.io/library/python:3.14-slim AS python-deps

WORKDIR /app

# Keeps Python from writing .pyc files & buffers output for Docker logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
#  Stage 3 — Production runtime (smallest image)
# ---------------------------------------------------------------------------
FROM docker.io/library/python:3.14-slim AS runtime

# System dependencies required by asyncpg at runtime.
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy Python site-packages from the deps stage.
COPY --from=python-deps /usr/local/lib/python3.14/site-packages/ /usr/local/lib/python3.14/site-packages/
COPY --from=python-deps /usr/local/bin/ /usr/local/bin/

# Copy the backend application code.
COPY backend/ ./

# Copy the pre-built frontend dist/ from the frontend builder stage.
COPY --from=frontend-builder /build/frontend/dist/ ./dist/

# ── Runtime ────────────────────────────────────────────────────────────────
EXPOSE 8000
CMD ["fastapi", "run", "--port", "8000", "--host", "0.0.0.0"]
