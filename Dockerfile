# --- 1. Frontend build -------------------------------------------------------
FROM node:22-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npx vite build

# --- 2. API + static frontend -----------------------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv

COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install ".[postgres]"
COPY alembic.ini ./
COPY migrations ./migrations
COPY --from=frontend /build/dist ./frontend

# Run as an unprivileged user
RUN useradd --system --uid 10001 appuser && mkdir -p /srv/var/uploads && chown -R appuser /srv/var
USER appuser

ENV APP_ENVIRONMENT=production APP_UPLOAD_DIR=/srv/var/uploads APP_FRONTEND_DIST=/srv/frontend
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --proxy-headers"]
