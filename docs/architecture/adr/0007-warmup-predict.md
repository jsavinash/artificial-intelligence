# ADR-0007: Warmup Predict at Load

- **Status:** Accepted
- **Date:** initial

## Context

Lazy initialization and shape/type mismatches in a serialized pipeline can
surface only on the first real request — turning a deploy-time bug into a
user-facing 500. We wanted load-time validation of the actual artifact.

## Decision

`ModelRuntime.load` runs a **warmup predict** on contract-shaped zeros
(`zeros((1, len(FEATURE_ORDER)))`) immediately after deserialization. Any
failure raises `ArtifactIntegrityError` and fails boot, so a mismatched
artifact is caught before it joins a load balancer.

## Consequences

- **Positive:** catches wrong feature counts, broken artifacts, and lazy-init
  crashes at deploy time, not request time.
- **Positive:** guarantees first real request never pays one-off init cost.
- **Negative:** adds a tiny one-time startup predict cost; for cold-slow
  models this could be non-trivial (acceptable here).