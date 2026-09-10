# Security

Security is treated as a first-class, continuous concern. This page covers the
threat model, what is implemented, and the hardening gaps that are accepted.

## 1. In-scope components

- Serving API (`apps/api`) — attack surface exposed to callers.
- Hardened container image (`infrastructure/Dockerfile`).
- CI/CD → artifact pipeline (integrity, supply chain).
- Training/export (running untrusted-looking-artifact load).
- Config/secrets handling (`common_lib.config`, environment).

## 2. Threat model (STRIDE-lite)

| Threat | Vector | Mitigation (current) | Gap / recommendation |
|---|---|---|---|
| **Spoofing** (fake caller) | Unauthorized POST /predict | None — internal service | **Add authN** at gateway: mTLS or service account token on internal net |
| **Tampering** (artifact) | Corrupt/modified artifact at boot | SHA-256 manifest verification (ADR-0003) | Authenticity: add keyed HMAC/signature if registry adversarial |
| **Repudiation** | No audit trail of who/what served | MLflow lineage, run_id in responses, structured logs | Optional access logs/WORM |
| **Information disclosure** | Data in logs/traces | Feature values not logged by default | Ensure callers never log payloads; PII review if features become PII |
| **DoS** | Large/expensive requests | Batch cap (1–1024), resource limits (2 CPU/1G) | Add rate limiting / concurrency control at gateway; load test p99 |
| **Elevation of privilege** | Container breakout | Non-root uid 10001, `no-new-privileges`, read-only artifact mount, minimal runtime image | NetworkPolicy, seccomp/AppArmor profiles |
| **RCE via artifact** | Malicious serialized object | `skops` with trusted-type allow-list (ADR-0002) | Keep allow-list minimal; code review on any entry |
| **Supply chain** | Compromised dependency/image | `uv.lock` frozen; `pip-audit` in CI; pinned image digests (`:v2.18.5`, `:v3.1.0`) | Pin digests; Dependabot/renovate; sign images (cosign) |

## 3. Implemented hardening

- **Deserialization:** `skops` + `_TRUSTED_TYPES` allow-list; unknown types refused.
- **Integrity:** streaming SHA-256 of artifact against `manifest.json`.
- **Container:** multi-stage slim runtime, **non-root** `USER 10001:10001`,
  no build toolchain or source copied in, `no-new-privileges:true`,
  read-only `/models:ro` mount, resource limits, `EXPOSE` only 8000.
- **Deploy (compose):** healthchecks, `restart: unless-stopped`, non-root.
- **Deposits/credentials:** `.env*`, `secrets/`, keys, certs ignored
  (`.gitignore`); `pip-audit` runs in CI.
- **Strict input validation:** Pydantic `extra="forbid"`, strict floats, range
  bounds, finiteness — limits abuse and malformed-data risk.

## 4. Secret management

- **Never** commit secrets; `.gitignore` excludes `.env*`, `secrets/`,
  `*.pem`, `*.key`, etc.
- Runtime config via `APP_*` env / secrets manager (Dynaconf reads env).
- CI: MLflow `TRACKING_URI` supplied via GitHub Actions secrets
  (`secrets.MLFLOW_TRACKING_URI`). Same for registry credentials at push.

## 5. Accepted risks / remediation plan

| Risk | Accept? | Plan |
|---|---|---|
| No authN on prediction endpoint | Yes (internal) for v1 | Add gateway authN (OIDC/mTLS) |
| SHA-256 integrity, not authenticity | Yes | Add keyed signature if adversarial artifact registry |
| No rate limiting | Yes (batch-bounded) | Gateway rate limit when externally exposed |
| Static image tags in compose (`:v2.18.5`) | Yes (dev) | Pin digests in prod; cosign signing |
| No network policy / seccomp | Yes (single-host) | Add on K8s |

## 6. Incident response pointer

Security-sensitive anomalies route to the on-call (see
[runbook](../operations/runbook.md) §10). For artifact integrity failures, do
**not** hand-edit manifests — re-export from the correct run.

---
*Next: [Production Readiness](production-readiness.md)*