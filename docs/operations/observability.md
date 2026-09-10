# Observability

The platform exposes **structured logs**, **HTTP + business metrics**, and
distributed tracing via `X-Request-ID`. This is the reference for what to
collect, and the alerting model.

## 1. Instrumentation points

| Concern | Mechanism | Source |
|---|---|---|
| Structured logs | `structlog` JSON → stdout | `common_lib.logging` |
| Per-route HTTP metrics | `prometheus-fastapi-instrumentator` | `api.main` |
| Business metrics | `prometheus_client` Counter/Histogram | `api.main` |
| Tracing/request correlation | `X-Request-ID` header | `api.main` middleware |

## 2. Metrics catalogue

### HTTP (from instrumentator, at `GET /metrics`)
Grouped by status code; latency and request counters per route:
- `http_requests_total{handler, method, status, ...}`
- `http_request_duration_seconds{handler, method, ...}`
- `/health` and `/metrics` are **excluded** from HTTP instrumentation.

### Business (custom)

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `model_predictions_total` | Counter | `model_version` | Predictions served per model version |
| `model_prediction_batch_size` | Histogram | — | Records per `/predict` batch (buckets up to 1024) |
| `model_inference_seconds` | Histogram | — | Pure `pipeline.predict()` time (excludes HTTP overhead) |

### Derived signals (alert candidates)
- **Readiness degradation:** probe `/ready` or scrape `http_requests_total{handler="/ready",status="503"}`.
- **Error rate:** `sum(rate(http_requests_total{handler!~"/health|/metrics",status=~"5.."}[5m])) / sum(rate(...))`.
- **Latency:** `histogram_quantile(0.99, sum by (le)(rate(http_request_duration_seconds_bucket[5m])))`.
- **Inference latency:** `histogram_quantile(0.99, model_inference_seconds_bucket)`.

## 3. Logging format

Single-line JSON per record, e.g.:

```json
{"timestamp":"2026-09-10T12:00:00Z","level":"info","service":"api",
 "message":"predict_served","batch_size":32,"model_version":"3f3c1afd",
 "inference_ms":1.204}
```

Key events: `logging_configured`, `loading_model`, `artifact_integrity_verified`,
`model_loaded`, `model_artifact_missing`, `predict_served`,
`training_complete`, `model_exported`.

## 4. Tracing model

- `X-Request-ID` is propagated (if supplied) or generated (`uuid4` hex, 32
  chars) by middleware and echoed on every response.
- It is **not** automatically injected into log records today (JSON args are
  explicit). If distributed tracing across hops is required, add a
  trace-id to the structured context and surface it in `/predict` logs and
  the `PredictionResponse`. (Future enhancement.)

## 5. Alerting rules (recommended)

| Alert | Expression | Severity | Notes |
|---|---|---|---|
| ServingDown | `up{job="serving-api"} == 0` | critical | Scrape target down |
| NotReady | `http_requests_total{handler="/ready",status="503"} > 0` | high | Artifact missing/degraded |
| High5xx | error-rate > 2% for 10m | high | Catch unexpected 500s |
| HighLatency | p99 HTTP > 2s for 10m | high | Model/CPU saturation |
| SlowInference | p99 `model_inference_seconds` > 0.5s | medium | Model-level regression |
| PredictionSurge | rate(`model_predictions_total`) > threshold | info | Volume anomaly / capacity |

## 6. Integration (Prometheus)

`infrastructure/prometheus.yml`:
- Job `serving-api` scrapes `api:8000/metrics` every 15s.
- Job `prometheus` scrapes itself.

Alertmanager + Grafana are not in this repo but are the natural owners of the
rules above.

---
*Next: [Runbook](runbook.md)*