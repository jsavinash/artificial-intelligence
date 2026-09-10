# Architecture Documentation — ML Platform

Authoritative documentation for the **ML Platform — Supervised Regression
Monorepo**. These documents are owned by the principal architect and are the
source of truth for *how* and *why* the system is built the way it is.

## Document Set

| Document | Purpose | Audience |
|---|---|---|
| [System Context](system-context.md) | The system and its external actors/dependencies (C4 Level 1). | Everyone |
| [High-Level Design](hld.md) | Container + component view, deployment topology, data flows (C4 Level 2). | Architects, SREs, backend |
| [Sequence Flows](sequence-flows.md) | End-to-end flows: training, export, serve, observability. | Backend, ML engineers |
| [Data Contracts](data-contracts.md) | The canonical feature/request/response contract — the anti-skew guarantee. | All engineers |
| [Architecture Decision Records (ADR)](adr/README.md) | Every significant decision, its context, options & consequences. | Architects |
| [Observability](../operations/observability.md) | Logging, metrics, tracing, alerting & dashboards. | SRE, backend |
| [Runbook](../operations/runbook.md) | Day-2 operational procedures: deploy, rollback, incident response. | On-call |
| [Deployment](../operations/deployment.md) | Environments, promotion policy, container & orchestration story. | SRE, platform |
| [Security](security.md) | Threat model, hardening, artifact integrity & secret handling. | Security, SRE |
| [Production Readiness](production-readiness.md) | Self-assessment against a production checklist. | Architect, SRE |
| [Testing Strategy](testing.md) | Unit/contract/smoke test coverage mapping to risk. | All engineers |

## How to read these documents

Start with **System Context** → **HLD** → **Sequence Flows**. Then drill into
**Data Contracts** and the **ADRs** for rationale. Use the **Runbook** the
moment you touch production.

## Conventions

- All diagrams are [Mermaid](https://mermaid.js.org/) so they stay versioned
  in git and render natively on GitHub.
- Any architectural change **must** be accompanied by an ADR before merging.
- The canonical feature contract in `libs/common/src/common_lib/schemas.py`
  is the single source of truth; documentation here must never contradict it.
- "Production-ready" is defined operationally by
  [Production Readiness](production-readiness.md), not by a branch name.

## Source of Truth Files

| Concern | File |
|---|---|
| Feature contract, request/response schemas | `libs/common/src/common_lib/schemas.py` |
| Structured logging | `libs/common/src/common_lib/logging.py` |
| Config layering | `libs/common/src/common_lib/config.py` |
| Model pipeline factory | `apps/pipelines/src/pipelines/model.py` |
| Training + MLflow tracking | `apps/pipelines/src/pipelines/train.py` |
| Artifact export + signing | `apps/pipelines/src/pipelines/export.py` |
| Serving runtime (load/verify/warmup) | `apps/api/src/api/runtime.py` |
| HTTP API + metrics | `apps/api/src/api/main.py` |
| Container + local stack | `infrastructure/` |
| CI/CD pipeline | `.github/workflows/ci.yml` |