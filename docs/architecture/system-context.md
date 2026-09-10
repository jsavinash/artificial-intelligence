# System Context Diagram (C4 Level 1)

The **ML Platform** is an enterprise MLOps monorepo that serves supervised
regression predictions over HTTP with a fully tracked, quality-gated and
integrity-verified model lifecycle. This is the highest-level view: the
system as a single box with its external dependencies.

```mermaid
flowchart LR
    subgraph external["External Actors"]
        CLIENT["🟢 Client / Downstream Service\nSends batch feature records for inference"]
        DS["🟢 Data Scientist\nWrites & maintains model code"]
        PLATFORM["🟢 Platform / SRE\nDeploys, operates, monitors"]
    end

    subgraph system["🟦 ML Platform (the system)"]
        PLATFORM_SYS["ML Platform\nTrain → Export → Serve pipeline"]
    end

    subgraph deps["External Dependencies"]
        GITHUB["⬜ GitHub\nSource control + CI/CD (Actions)"]
        MLFLOW["⬜ MLflow Tracking Server\nExperiment store + artifact backend"]
        PROM["⬜ Prometheus\nMetrics store & alerting"]
        DOCKER["⬜ Docker / Container Runtime"]
    end

    CLIENT -->|"POST /predict (HTTPS)"| PLATFORM_SYS
    PLATFORM_SYS -->|"metrics (pull)"| PROM
    PLATFORM_SYS -->|"read/write runs & artifacts"| MLFLOW
    DS -->|"push code"| GITHUB
    GITHUB -->|"CI/CD: lint/test/train/build"| PLATFORM_SYS
    GITHUB -->|"orchestrates"| MLFLOW
    PLATFORM_SYS -->|"container image"| DOCKER
    PLATFORM -->|"deploy & operate containers"| DOCKER
    PLATFORM -->|"on-call dashboards"| PROM
```

## Key Facts

- **Purpose:** Serve low-latency batch regression predictions with
  reproducible, auditable training.
- **Primary callers:** Downstream services (machine-to-machine, HTTPS).
- **Runtime tech:** Python 3.12, FastAPI + Uvicorn, scikit-learn (Ridge +
  StandardScaler), NumPy, `skops` serialization, Prometheus instrumentation.
- **Model:** California Housing regression restricted to 3 canonical features
  (`med_inc`, `house_age`, `avg_occupancy`).
- **Not in scope:** No UI, no authN/authZ of callers (service-to-service on an
  internal network — see [Security](security.md)), no multi-model registry
  routing, no online feature store.

## External Dependency Contracts

| Dependency | Interaction | Failure mode | Mitigation |
|---|---|---|---|
| GitHub | Push code; CI/CD triggers on `main` | CI unavailable → no deploy | Branch protection gating |
| MLflow | Log runs, metrics, artifacts; download artifact at export | Server down → training falls back to local sqlite (`--allow-fallback`) | Fallback URI, offline artefact export |
| Prometheus | Pulls `/metrics` every 15s | Metrics gap → degraded observability only (non-critical path) | Redundant scrape target |
| Docker | Image build & runtime | — | Multi-stage, non-root, healthcheck |

## Explicit Dependencies the System Does NOT Own

- **MLflow server** and **Prometheus** are independently operated;
  `docker-compose` provides a local reference implementation.
- The model artifact **source of truth** is the MLflow artifact backend; the
  `artifacts/` directory is a derived, signed promotion copy.

---
*Next: [High-Level Design](hld.md)*