# ADR-0005: Boot Tolerant of Missing Artifact, Gate via Readiness

- **Status:** Accepted
- **Date:** initial

## Context

If the model artifact is absent, two options: crash at boot (fast fail) or
run degraded. Crashing guarantees we never serve without a model, but makes
deployment ordering brittle (must guarantee artifact before pod start) and
harder to diagnose.

## Decision

The API **boots even when the artifact is missing**: `lifespan` catches
`FileNotFoundError`, logs `model_artifact_missing`, and leaves the runtime
unloaded. `/health` reports `not-ready`, `/ready` returns **503**, and
`/predict` returns **503** — so the orchestrator keeps the pod out of
service until a valid artifact is available, but the process is inspectable.

## Consequences

- **Positive:** clearer ops story — deploy and artifact provisioning are
  decoupled; `/ready` drives routing.
- **Positive:** missing artifact is visible (503 + logs) instead of a crash
  loop.
- **Negative:** an operator may see a running-but-not-ready pod; requires
  correct readiness-probe wiring to be effective (documented in
  [deployment](../../operations/deployment.md)).