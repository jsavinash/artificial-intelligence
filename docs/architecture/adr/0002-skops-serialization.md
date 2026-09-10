# ADR-0002: skops for Artifact Serialization

- **Status:** Accepted
- **Date:** initial

## Context

`pickle`/`cloudpickle` can execute arbitrary code on load (RCE risk) and are
fragile across environments. `joblib` extends this. `dill` similar. We need a
secure, version-safe way to serialize a fitted `sklearn.Pipeline`.

## Decision

Use **`skops`** `skio.dump`/`skio.load` with an explicit allow-list of trusted
types (`_TRUSTED_TYPES` = `StandardScaler`, `Ridge`, `numpy.dtype`) at load.
Unknown or unsafe types are rejected.

## Consequences

- **Positive:** mitigates pickle RCE; explicit trusted-type model.
- **Positive:** model-only format — schema/version drift surfaced at load.
- **Negative:** only serializes objects whose types are trusted; more
  complex/custom transformers must be added to the allow-list consciously —
  an explicit, auditable process.