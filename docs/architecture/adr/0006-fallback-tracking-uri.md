# ADR-0006: MLflow Tracking with Local Fallback

- **Status:** Accepted
- **Date:** initial

## Context

Training requires MLflow for lineage. But a hard dependency means a tracking
server outage blocks all training. For a dev loop / resilience we wanted a
degraded path.

## Decision

`pipelines.train` takes `--tracking-uri` (default `http://localhost:5000`)
plus `--allow-fallback` and `--fallback-uri`
(`sqlite:////tmp/mlflow.db`). On primary failure with the flag set, it retries
against sqlite. Without the flag, it fails fast (exit `1`).

## Consequences

- **Positive:** resilient local/dev training; no server required for a basic
  loop.
- **Positive:** production CI can still mandate the real server (no flag) for
  full lineage.
- **Negative:** fallback runs live in a different store — lineage is split,
  so operators must export/merge if a fallback run is promoted. Use fallback
  for development, real server for promotion-critical training.