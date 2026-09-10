# ADR-0004: Runtime Quality Gate on Test R²

- **Status:** Accepted
- **Date:** initial

## Context

Regressions can be trained accidentally. Without a gate, a bad model can be
exported and promoted to production. We needed a promotion barrier.

## Decision

`pipelines.train` computes test metrics (rmse, mae, r2) and tags the MLflow
run with `quality_gate` (`pass`/`fail`). The CLI exits `2` when
`r2 < --min-r2` (default `0.40`). The promotion/export step should only run
against a passing run (CI orders it after `quality`).

## Consequences

- **Positive:** automated rejection of models below the metric floor.
- **Positive:** gate value is configurable and logged for audit; failure is
  loud (non-zero exit) rather than silent.
- **Negative:** a single metric gate can be gamed/tuned; it is a floor, not a
  substitute for business evaluation.