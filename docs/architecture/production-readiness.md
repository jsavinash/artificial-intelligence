# Production Readiness Assessment

Operational self-assessment of the ML Platform against a production checklist.
Each item is marked **Implemented**, **Partial**, or **Gap** with a pointer to
evidence or remediation. This is a living document owned by the principal
architect + SRE.

## 1. Reliability & Resilience

| Area | Status | Evidence / Note |
|---|---|---|
| Graceful degradation (missing model) | ✅ Implemented | ADR-0005; `/ready`/`/predict` 503, `/health` `not-ready` |
| Artifact integrity verification | ✅ Implemented | ADR-0003 SHA-256 + manifest |
| Boot-time warm-up catches skew | ✅ Implemented | ADR-0007 warmup predict |
| Readiness vs liveness split | ✅ Implemented | `/ready` (503) vs `/health` (always-up) |
| MLflow fallback path | ✅ Implemented | ADR-0006 `--allow-fallback` |
| Resource limits | ✅ Implemented | compose 2 CPU / 1G; batch cap 1024 |
| Redundancy / HA (multi-instance) | ⚠️ Partial | Stateless → easy; target K8s HPA. Local compose is single-instance |
| Load/stress tested to SLI | ⚠️ Gap | No baked load test; add locust/k6 + assert p99 |

## 2. Observability

| Area | Status | Evidence |
|---|---|---|
| Structured logging | ✅ | structlog JSON; `service`, `timestamp`, level |
| HTTP metrics | ✅ | Instrumentator at `/metrics` |
| Business metrics | ✅ | predictions/batch/inference histograms |
| Request correlation | ✅ | `X-Request-ID` propagated/assigned |
| Tracing/correlation into logs | ⚠️ Partial | Header only; trace-id not yet injected into JSON |
| Distributed tracing (OTel) | ❌ Gap | Not implemented; optional enhancement |
| Alerting | ⚠️ Partial | Rules recommended; alertmanager/grafana not in repo |

## 3. Security (details in [security.md](security.md))

| Area | Status | Evidence |
|---|---|---|
| Non-root container | ✅ | `USER 10001:10001`, CI asserts |
| No build toolchain in runtime | ✅ | Multi-stage |
| Secure deserialization | ✅ | skops + allow-list |
| No secrets in git | ✅ | `.gitignore` + CI uses GH secrets |
| Dependency scanning | ✅ | `pip-audit` in CI |
| AuthN on endpoint | ❌ Gap | Internal-only for v1; add gateway authN |
| Rate limiting | ❌ Gap | Batch-capped; add gateway when exposed |
| Image signing / pinned digests | ❌ Gap | Pin digests + cosign in prod |

## 4. CI/CD & Change Management

| Area | Status | Evidence |
|---|---|---|
| Automated quality gates | ✅ | lint/format/mypy/audit/tests cov>70 |
| Model quality gate | ✅ | R² floor; exit 2; tagged run |
| Container build + smoke test | ✅ | multi-stage + live smoke (ready/predict/non-root) |
| Reproducible builds | ✅ | frozen `uv.lock` |
| Branch protection on main | ⚠️ Partial | Recommended; verify in repo settings |
| Approval for prod deploy | ⚠️ Partial | Policy documented; tooling up to platform |

## 5. Testing (details in [testing.md](testing.md))

| Area | Status | Evidence |
|---|---|---|
| Unit tests | ✅ | 26 tests, ~99% coverage |
| Contract (validation) tests | ✅ | schema edge cases, 422 paths |
| Startup/load-failure path | ✅ | `test_not_ready_returns_503`, runtime integrity tests |
| E2E smoke | ✅ | CI live serving smoke; `make smoke` |
| Performance/load tests | ❌ Gap | Add k6/locust + budgets |
| Property/fuzz tests | ❌ Gap | Optional; consider `hypothesis` for schema |

## 6. Documentation & Operational Readiness

| Area | Status | Evidence |
|---|---|---|
| Architecture docs | ✅ | this suite |
| Runbook | ✅ | [operations/runbook.md](../operations/runbook.md) |
| Deployment doc | ✅ | [operations/deployment.md](../operations/deployment.md) |
| On-call playbook/alert definitions | ⚠️ Partial | Rules; alertmanager wiring required |
| Post-incident review process | ❌ Gap | Define SLOs/error budget + blameless PIR |

## 7. SLO / Error Budget (recommended)

TBD with product/business — proposal:

| SLI | SLO (30d) |
|---|---|
| Availability (`p95` healthy `/ready` resp under 500ms) | 99.9% |
| `p99` prediction latency | < 2s |
| Success rate (non-5xx) on `/predict` | 99.5% |
| Training success (quality gate passes) | 95% (roll month) |

## Prioritized gap backlog

1. **Load/perf test** + p99 budgets (High).
2. **Alertmanager/Grafana** wiring + SLO config (High).
3. **Branch protection + required checks** on `main` (High).
4. **Gateway authN + rate limiting** when externally reachable (Medium).
5. **Distributed tracing injection into logs** (Medium).
6. **Feedback PIR process + error budgets** (Medium).

---
*Next: [Testing Strategy](testing.md)*