# syntax=docker/dockerfile:1.9
# ---------------------------------------------------------------------------
# Multi-stage build: builder installs deps into a venv; runtime copies only
# the venv, runs as non-root, no build toolchain or source in the final image.
# `--no-editable` is critical: workspace members are installed as regular
# wheels so nothing references builder-stage paths at runtime.
# ---------------------------------------------------------------------------
ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim AS builder
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
COPY libs/common/pyproject.toml libs/common/pyproject.toml
COPY apps/pipelines/pyproject.toml apps/pipelines/pyproject.toml
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY libs/ libs/
COPY apps/ apps/
RUN uv sync --frozen --no-dev --no-editable --package api

# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime
LABEL org.opencontainers.image.title="ml-platform-api" \
      org.opencontainers.image.description="Low-latency regression serving API" \
      org.opencontainers.image.source="https://github.com/example/ml-platform" \
      org.opencontainers.image.licenses="proprietary"
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MODEL_ARTIFACT_PATH=/models/pipeline.skops
RUN groupadd --gid 10001 appgroup && \
    useradd --uid 10001 --gid appgroup --no-create-home --shell /usr/sbin/nologin appuser
COPY --from=builder /opt/venv /opt/venv
USER 10001:10001
WORKDIR /app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--no-access-log"]
