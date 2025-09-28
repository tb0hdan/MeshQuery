# syntax=docker/dockerfile:1.7
FROM python:3.13-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1

# System deps for psycopg2 and healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project
COPY . /app/

# Install the package (pyproject.toml)
RUN python -m pip install --upgrade pip && \
    python -m pip install .

EXPOSE 8080
# Compose selects the command for each service
