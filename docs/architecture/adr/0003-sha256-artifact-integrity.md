# ADR-0003: SHA-256 Signed Artifact Manifests

- **Status:** Accepted
- **Date:** initial

## Context

Artifacts move from MLflow through CI into production mounts. Corrupt or
tampered artifacts could silently serve wrong predictions. We wanted
integrity verification without a heavyweight signing/PKI setup.

## Decision

`pipelines.export` writes `manifest.json` containing a **streaming SHA-256**
of the artifact plus run metadata. At load, `ModelRuntime.load` recomputes the
hash and raises `ArtifactIntegrityError` on mismatch.

## Consequences

- **Positive:** detects corruption/tampering at load; cheap and fast.
- **Positive:** run-id lineage (version) surfaces in `/health` and `/ready`.
- **Negative:** SHA-256 is integrity (not authenticity) — it does not prove
  origin. Real authentication would need keyed signatures (future ADR if
  adversarial artifact registry becomes a threat).