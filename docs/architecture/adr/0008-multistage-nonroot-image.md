# ADR-0008: Multi-Stage, Non-Root Container Image

- **Status:** Accepted
- **Date:** initial

## Context

Serving images commonly leak build toolchain, run as root, and reference
builder-stage paths. We wanted a defensible, production-grade image.

## Decision

The `infrastructure/Dockerfile`:

- **Builder stage:** installs deps into `/opt/venv`, compiles bytecode, uses
  `uv sync --frozen --no-dev --no-editable --package api` — wheels are built
  `--no-editable` so no builder-stage source paths leak into runtime.
- **Runtime stage:** slims (no build tools/source), runs as
  `USER 10001:10001`, sets `MODEL_ARTIFACT_PATH=/models/pipeline.skops`,
  `EXPOSE 8000`, declares a `HEALTHCHECK`, launches uvicorn with 2 workers.

## Consequences

- **Positive:** rootless runtime, minimal attack surface, reproducible frozen
  build, self-describing healthcheck.
- **Positive:** CI smoke test asserts the image user is `10001:10001`.
- **Negative:** every dependency requires a rebuild (frozen); larger CI build
  time; multi-stage adds Docker build complexity.