# Production Dockerfile for Storage Lifecycle Optimizer Backend
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install system dependencies required for PostgreSQL & build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency requirements
COPY backend/pyproject.toml /app/

# Install python dependencies via pip
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir fastapi uvicorn sqlalchemy psycopg2-binary alembic pydantic boto3 pytest

# Copy backend codebase
COPY backend/ /app/

# Expose backend API port
EXPOSE 8000

# Startup command running database migration then starting Uvicorn server
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
