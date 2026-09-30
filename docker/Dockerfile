# KavachAI — offline AI-assurance workbench (prototype)
#
# Multi-stage build:
#   1. frontend-build — compile the React+Vite SPA to static assets
#   2. runtime        — Python API + backend + prebuilt SPA (served at /)
#
# The image is fully offline at runtime: no cloud APIs, no external services.

# ---- Stage 1: build the frontend -------------------------------------------
FROM node:24-slim AS frontend-build
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: runtime -------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps: libgomp for scikit-learn, curl for the healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --from=frontend-build /fe/dist ./frontend/dist
COPY backend/ ./backend/
COPY ml/ ./ml/
COPY attack_generator/ ./attack_generator/
COPY scripts/ ./scripts/
COPY models/ ./models/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -sf http://127.0.0.1:8000/api/v1/health || exit 1

# Seed demo models/datasets on first boot, then serve the API + SPA.
# NOTE: the SQLite DB (kavach.db) lives inside the container and is
# ephemeral; generated datasets and reports are persisted via volumes.
CMD ["sh", "-c", "python scripts/seed_all.py && python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"]
