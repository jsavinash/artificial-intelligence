# High-Level Design (C4 Level 2) — Containers & Components

This is the principal design document. It describes the container topology,
component responsibilities, deployment models, and the primary data flows.

---

## 1. Container Diagram

Four deployable units plus the CI runtime:

```mermaid
flowchart TB
    subgraph client["Clients"]
        CALLER["🟢 API Caller\nPost /predict batches"]
    end

    subgraph net["Network"]
        LB["⬜ Internal Load Balancer / Gateway\nTerminates TLS, X-Request-ID"]
    end

    subgraph docker["Container orchestration (Docker / K8s-style pods)"]
        API["🟦 [Container] Serving API\nFastAPI + Uvicorn (2 workers)\nRESPONSIBLE: in-memory inference"]
        PROM["🟪 [Container] Prometheus\nscrape :8000/metrics"]
        MLFLOW["🟪 [Container] MLflow Server\n:5000 runs/artifacts"]
    end

    subgraph storage["Storage"]
        ART["🟨 [Volume] Model Artifacts\nread-only mount\nartifacts/latest/pipeline.skops"]
        MLDATA["🟨 [Volume] MLflow data\nsqlite + artifacts"]
        PROMDATA["🟨 [Volume] Prometheus data"]
    end

    subgraph ci["CI/CD (GitHub Actions)"]
        CI["🟦 [Job] ci-cd\nquality → train-and-export → docker-build"]
    end

    CALLER --> LB --> API
    API -->|"loads into memory once"| ART
    API -->|"GET /metrics"| PROM
    PROM --> PROMDATA
    MLFLOW --> MLDATA
    CI -->|"trains + exports signed artifact"| MLFLOW
    CI -->|"builds image, pushes registry"| API
    MLFLOW -->|"serves run lineage"| API
```

At runtime the **API container** is the only always-on component; MLflow and
Prometheus are supporting services (long-lived in the reference stack).

---

## 2. Component Diagram — Serving API

Internal structure of the API container:

```mermaid
flowchart LR
    subgraph api["[Container] Serving API"]
        FASTAPI["FastAPI app\n(lifespan, routing, middleware)"]
        RUNTIME["ModelRuntime\nload→verify→warmup\nin-memory predict"]
        METRICS["prometheus_client\nCounters/Histograms + Instrumentator"]
        LOG["structlog JSON\nstdout"]
        SCHEMAS["common_lib.schemas\nPydantic v2 contracts"]
    end

    subgraph artifact["[External] Artifact"]
        PIPE["pipeline.skops\n(sklearn Pipeline: scale→Ridge)"]
        MANIFEST["manifest.json\nSHA-256, metrics, run_id"]
    end

    subgraph sysinfo["[System]"]
        ENV["MODEL_ARTIFACT_PATH\nconfig"]
    end

    FASTAPI -->|"GET /health /ready"| RUNTIME
    FASTAPI -->|"POST /predict"| RUNTIME
    RUNTIME -->|"reads + verifies"| PIPE
    RUNTIME -->|"reads manifest"| MANIFEST
    FASTAPI --> METRICS
    FASTAPI --> LOG
    FASTAPI --> SCHEMAS
    RUNTIME --> SCHEMAS
    ENV --> RUNTIME
```

### Component Responsibilities

| Component | Responsibility | Key detail |
|---|---|---|
| `main.py` (FastAPI) | HTTP interface, lifecycle, request-ID propagation, route-level metrics | Lifespan loads model once; boot is **tolerant** of missing artifact (readiness 503) |
| `runtime.py` (ModelRuntime) | Load artifact, validate integrity, warm-up, batch predict | `skops` deserialization with `_TRUSTED_TYPES` allow-list; warmup catches train/serve skew |
| `schemas.py` | Canonical contracts | `FeatureRecord`, `PredictionRequest/Response`, `HealthResponse`; `extra="forbid"`, strict floats, range bounds |
| `Instrumentator` | Per-route HTTP metrics | Groups status codes, ignores untemplated paths |
| `structlog` | Structured JSON logging | Single-line records, `service` field, ISO timestamps UTC |
---

## 3. Component Diagram — Pipelines

```mermaid
flowchart LR
    subgraph pipe["[Container] Pipelines (offline)"]
        MODEL["model.py\nbuild_pipeline(): StandardScaler→Ridge"]
        TRAIN["train.py\nload→split→fit→metric→log→serialize"]
        EXPORT["export.py\ndownload→sign→promote"]
        CONTRACT["common_lib.schemas\nFeatureRecord (FEATURE_ORDER)"]
    end

    subgraph svc["External"]
        ML["🟪 MLflow (server)"]
        SKOPS["skops serialize\n(pipeline.skops)"]
    end

    CONTRACT --> MODEL
    MODEL --> TRAIN
    TRAIN -->|"log params/metrics/artifact + signature"| ML
    TRAIN --> SKOPS
    EXPORT -->|"download latest run"| ML
    EXPORT -->|"write artifacts/<run>/manifest.json + latest symlink"| ART2
    subgraph art2["artifacts/"]
        ART2["<run-id>/pipeline.skops + manifest.json"]
    end
```

---

## 4. Deployment Topologies

### 4.1 Local Development (docker-compose reference stack)

`make stack-up` runs three containers: `api`, `mlflow`, `prometheus` with
named volumes. The API mounts `../artifacts:/models:ro`.

```
┌─────────────┐   ┌──────────────┐   ┌──────────────┐
│ api:8000    │ → │ mlflow:5000  │   │ prometheus    │
│ (artifacts)->/models:ro        │   │ scrapes api   │
└─────────────┘   └──────────────┘   └──────────────┘
```

### 4.2 Production target (conceptual)

- **Serving:** replicated API pods behind a load balancer / service mesh
  (e.g. Kubernetes `Deployment`, `HorizontalPodAutoscaler`), TLS terminated
  at the gateway.
- **Readiness/liveness:** `/ready` (503 until model warm) drives readiness
  probe; `/health` drives liveness.
- **Artifact distribution:** CI exports the signed artifact and mounts it into
  new pods **read-only** via a projected volume / init-container at deploy
  time (not live-updated in place) — keeping immutability of serving pods.
- **Observability:** Prometheus pulls `/metrics`; alerts defined in
  [observability](../operations/observability.md).
- **Model update flow:** atomic via symlink swap (`artifacts/latest`) or new
  pod rollout; see [deployment](../operations/deployment.md).

### 4.3 Scaling behaviour

- **Stateless** inference workers — horizontal scale is trivial.
- Artifact loaded once per process; memory = artifact working set + overhead.
- Batch size is bounded (1–1024 records) to protect memory/latency.
- `deploy.resources.limits` (cpus 2.0, memory 1G) set in compose as a guard.

---

## 5. Data / Control Flow Summary

| # | Flow | Path | Async? |
|---|---|---|---|
| 1 | Train | `main → load_data → train → MLflow (fallback sqlite) → skops dump` | No |
| 2 | Export | `export → MLflow download → manifest(SHA-256) → latest symlink swap` | No |
| 3 | Serve startup | `lifespan → resolve path → load → verify → warmup → set_runtime` | No |
| 4 | Predict request | `POST /predict → validate → records_to_matrix → predict → metrics → response` | No |
| 5 | Observability | `request → Instrumentator + counters → /metrics scrape` | Async pull |

---

## 6. Failure Semantics (summary)

| Failure | Symptom | Behaviour |
|---|---|---|
| Artifact missing | `FileNotFoundError` at startup | App **boots**; `/ready` 503; `/predict` 503; `/health` `not-ready` |
| Artifact tampered | SHA-256 mismatch | `ArtifactIntegrityError`; boot fails (kept out of LB) |
| Artifact wrong shape | Warmup predict fails | `ArtifactIntegrityError`; boot fails — prevents train/serve skew silently |
| MLflow down at train | `ConnectionError` | Train exits 1 unless `--allow-fallback` → sqlite |
| Malformed request | 422 (Pydantic) | Client error, no inference |
| No model loaded (after reset) | `ModelNotLoadedError` | 503 |

See [Runbook](../operations/runbook.md) for diagnosis steps.

---
*Next: [Sequence Flows](sequence-flows.md)*
| `Dynaconf config` | Config layering | `APP_*` env beats `settings.toml`; optional file, never fatal |