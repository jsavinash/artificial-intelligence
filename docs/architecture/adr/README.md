# Architecture Decision Records

ADRs capture **why** we built things this way, so future engineers and the
principal architect can evaluate trade-offs without re-litigating them. Each
ADR is immutable once merged; superseded ones are marked `Superseded by`.

## Convention

- Follow [MADR](https://adr.github.io/madr/) lightweight template.
- Numbered `NNNN-descriptive-slug.md`.
- New decisions on the model/contract/deployment **must** add an ADR.

## Register

| ADR | Title | Status | Decides |
|---|---|---|---|
| [0001](0001-single-feature-contract.md) | Single canonical feature contract (anti-train/serve-skew) | Accepted | Schemas + feature order |
| [0002](0002-skops-serialization.md) | skops over pickle/joblib for artifact persistence | Accepted | Artifact format |
| [0003](0003-sha256-artifact-integrity.md) | SHA-256 signed manifests for artifact integrity | Accepted | Export + load verification |
| [0004](0004-quality-gate.md) | Runtime quality gate on test R² | Accepted | Training exit code / promotion |
| [0005](0005-boot-tolerant-of-missing-artifact.md) | Boot despite missing artifact, gate readiness | Accepted | Startup/failure semantics |
| [0006](0006-fallback-tracking-uri.md) | MLflow fallback to local sqlite | Accepted | Training resilience |
| [0007](0007-warmup-predict.md) | Warmup predict at load to catch train/serve skew | Accepted | Load path |
| [0008](0008-multistage-nonroot-image.md) | Multi-stage, non-root container image | Accepted | Dockerfile |
| [0009](0009-uv-workspace-monorepo.md) | uv workspace monorepo layout | Accepted | Repo layout + build |
| [0010](0010-structured-json-logging.md) | Structured JSON logging (structlog) | Accepted | Logging |