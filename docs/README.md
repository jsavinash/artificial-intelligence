# Documentation

Central entry point for all platform documentation.

## Architecture & Design

> Owned by the principal architect. Explains *how* and *why* the system is
> built. Start here.

- [Index](architecture/README.md)
- [System Context](architecture/system-context.md) — the system and its actors (C4 L1)
- [High-Level Design](architecture/hld.md) — containers, components, topology (C4 L2)
- [Sequence Flows](architecture/sequence-flows.md) — train/export/serve/observe
- [Data Contracts](architecture/data-contracts.md) — canonical schemas
- [Architecture Decision Records](architecture/adr/README.md) — 10 ADRs
- [Security](architecture/security.md) — threat model + hardening
- [Production Readiness](architecture/production-readiness.md) — assessment & gap backlog
- [Testing Strategy](architecture/testing.md) — test mapping + gaps

## Operations

- [Index](operations/README.md)
- [Observability](operations/observability.md)
- [Runbook](operations/runbook.md)
- [Deployment](operations/deployment.md)

## Project

- [README](../README.md) — quickstart, layout, make targets
- `pyproject.toml` / `Makefile` / `.github/workflows/ci.yml` — tooling & CI