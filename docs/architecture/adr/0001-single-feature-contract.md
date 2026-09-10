# ADR-0001: Single Canonical Feature Contract

- **Status:** Accepted
- **Date:** initial
- **Deciders:** Principal Architect

## Context

Training code (California Housing) and serving code (FastAPI) both need the
set of input features. If they read different columns, or read them in
different order, the model silently serves garbage. We needed one definition.

## Decision

Define `FeatureRecord` (with `FEATURE_ORDER`) once in
`common_lib.schemas` and derive **both** serving (`records_to_matrix` in
`api.runtime`) and training (`load_data` in `pipelines.train`,
`as_matrix`/records_to_matrix in `pipelines.model`) from it. Training restricts
its dataset to exactly `FEATURE_ORDER` via an explicit name mapping.

## Consequences

- **Positive:** train/serve skew by column order is structurally impossible;
  the request schema and artifact signature share the contract.
- **Positive:** adding/removing a feature is a single-field change with
  compile-time (mypy) and test coverage.
- **Negative:** requires retraining + re-export on any feature change; a
  breaking contract change must be a coordinated release (see
  [data-contracts](../data-contracts.md)).