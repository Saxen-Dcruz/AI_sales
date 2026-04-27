# Use the official slim Python image
FROM python:3.11-slim

WORKDIR /app

# 1. Install system dependencies
# - curl: For healthchecks
# - gcc / libpq-dev: Required for compiling Postgres drivers
# - Playwright/Chromium runtime deps: all libraries Chromium needs in headless mode
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    libpq-dev \
    # Playwright / Chromium headless deps
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdbus-1-3 libdrm2 libxkbcommon0 \
    libatspi2.0-0 libx11-6 libxcomposite1 libxdamage1 \
    libxext6 libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Python dependencies
COPY requirements.txt .
RUN pip install --default-timeout=1000 --no-cache-dir -r requirements.txt

# 3. Download Playwright Chromium browser (headless mode — no display needed)
RUN python -m playwright install chromium


# 4. Copy your application code
COPY . .

# 5. Expose the port and start FastAPI
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]