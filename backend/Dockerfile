# =============================================================================
# Backend image — FastAPI + Playwright/Chromium
# Targets:
#   development -> hot-reload (uvicorn --reload), code bind-mounted by compose
#   production  -> non-root, multi-worker uvicorn, no reload  (DEFAULT / last stage)
# =============================================================================

# --- STAGE 1: Base (system deps + Python deps + Chromium) -------------------
FROM python:3.14-slim AS base

WORKDIR /app

# System dependencies:
# - curl: healthchecks
# - gcc / libpq-dev: compile Postgres drivers
# - the libXXX set: Chromium headless runtime libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdbus-1-3 libdrm2 libxkbcommon0 \
    libatspi2.0-0 libx11-6 libxcomposite1 libxdamage1 \
    libxext6 libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies (cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --default-timeout=1000 --no-cache-dir -r requirements.txt

# Chromium for Playwright (headless). Installed to a shared, world-readable path
# so a non-root runtime user can still launch it.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN python -m playwright install chromium \
    && chmod -R a+rx /ms-playwright

# Application code
COPY . .

EXPOSE 8000

# --- STAGE 2: Development ----------------------------------------------------
# Hot-reload server. Compose bind-mounts ./backend over /app so edits reload.
FROM base AS development
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# --- STAGE 3: Production (DEFAULT) -------------------------------------------
# Non-root, multi-worker, no reload. Worker count tunable via WEB_CONCURRENCY.
FROM base AS production

# Run as an unprivileged user; give it ownership of app + browser cache.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app /ms-playwright
USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# sh -c so ${WEB_CONCURRENCY} expands at runtime (defaults to 2 workers).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-2}"]
