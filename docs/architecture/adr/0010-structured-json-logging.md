# ADR-0010: Structured JSON Logging (structlog)

- **Status:** Accepted
- **Date:** initial

## Context

Line-oriented stdout logging is hard to aggregate, correlate, and alert on in
production. We needed consistent, machine-readable, request-correlatable logs.

## Decision

Use **`structlog`** via `common_lib.logging.configure_logging(service=...)`
to emit single-line JSON records to stdout (`sys.stdout`, `force=True`),
including `timestamp` (ISO, UTC), `level`, `service`, and event fields.
Context is bound per-service via `get_logger(service=...)`. Access-log noise
(`uvicorn.access`) is suppressed to avoid duplication.

## Consequences

- **Positive:** structured, aggregator-friendly (Datadog/ELK/GCP), with a
  `service` field for routing; easy to add fields.
- **Positive:** `X-Request-ID` + structured fields enable end-to-end
  correlation.
- **Negative:** JSON logs are less human-friendly in raw form; consistent
  context binding is a team discipline. Config is idempotent per process.