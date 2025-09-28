# syntax=docker/dockerfile:1.7
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS base
WORKDIR /app
ENV UV_SYSTEM_PYTHON=1 PIP_NO_CACHE_DIR=1 PYTHONUNBUFFERED=1

# Bring in manifests if present
COPY pyproject.toml uv.lock* requirements*.txt LICENSE README.md ./

# Install dependencies (robust to lock/no-lock)
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ -f pyproject.toml ] && [ -f uv.lock ]; then \
        echo "===> uv sync (locked)"; \
        uv sync --frozen --no-dev; \
    elif [ -f requirements.txt ]; then \
        echo "===> uv pip install -r requirements.txt"; \
        uv pip install -r requirements.txt; \
    elif [ -f pyproject.toml ]; then \
        echo "===> uv pip install . (no lock)"; \
        if [ ! -f LICENSE ]; then echo "MIT License (placeholder for build)" > LICENSE; fi; \
        if [ ! -f README.md ] && [ ! -f README.rst ]; then echo "# Placeholder README" > README.md; fi; \
        uv pip install .; \
    else \
        echo "No pyproject.toml or requirements.txt found"; \
        exit 1; \
    fi

# Copy whole repo (covers package-at-root, src/, malla/src/)
COPY . /app
ENV PYTHONPATH=/app:/app/src:/app/malla/src

# ---- Capture image
FROM base AS malla-capture
CMD ["python", "-m", "malla.mqtt_capture"]

# ---- Web image
FROM base AS malla-web
EXPOSE 8080
# CMD ["gunicorn", "-b", "0.0.0.0:8080", "malla.wsgi:application"]  # if you ship gunicorn
CMD ["python", "-m", "malla.wsgi"]
