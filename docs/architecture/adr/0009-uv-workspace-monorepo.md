# ADR-0009: uv Workspace Monorepo

- **Status:** Accepted
- **Date:** initial

## Context

The platform has three logical packages (`api`, `pipelines`, `common-lib`)
that share dependencies and must be versioned/deployed together. We needed a
monorepo layout with reproducible dependency resolution.

## Decision

Adopt a **uv workspace monorepo**: root `pyproject.toml` (virtual package,
`package = false`) with `tool.uv.workspace.members = ["libs/*", "apps/*"]`,
per-package hatch build-backends, and a committed, frozen `uv.lock`. All
commands run through `uv run --package <name>`. Cross-package deps are
workspace references.

## Consequences

- **Positive:** one lockfile, reproducible frozen installs, easy cross-app
  reuse of `common-lib`.
- **Positive:** `--no-editable` builds produce relocatable wheels for the
  container.
- **Negative:** coupling — a change to `common-lib` rebuilds dependents;
  requires discipline to keep package boundaries clean.