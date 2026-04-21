# Use the official slim Python image
FROM python:3.11-slim

WORKDIR /app

# 1. Install system dependencies
# - curl: For your docker-compose healthchecks
# - gcc & libpq-dev: Required for compiling Postgres drivers (psycopg) securely
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Python dependencies
COPY requirements.txt .
RUN pip install --default-timeout=1000 --no-cache-dir -r requirements.txt


# 4. Copy your application code
COPY . .

# 5. Expose the port and start FastAPI
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]