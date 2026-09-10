# Sequence Flows — End-to-End

The complete lifecycle, rendered as sequence diagrams. Covers the three
offline stages plus the online inference and observability paths.

---

## 1. Training

```mermaid
sequenceDiagram
    autonumber
    participant DS as Data Scientist
    participant P as pipelines.train
    participant CL as common_lib.schemas
    participant M as MLflow Server
    participant S as skops

    DS->>P: python -m pipelines.train --alpha 1.0
    P->>CL: load_data() uses FeatureRecord.FEATURE_ORDER
    Note over P,CL: Restricts California Housing to med_inc, house_age, avg_occupancy
    P->>P: train_test_split(seed=42)
    P->>P: build_pipeline() → StandardScaler→Ridge
    P->>M: set_tracking_uri / set_experiment(supervised-regression)
    P->>M: start_run(ridge-alpha-1.0)
    P->>P: fit(x_train, y_train)
    P->>P: compute predictions on x_test
    P->>M: log_params(params)
    P->>M: log_metrics(metrics)
    P->>S: skio.dump(pipeline, pipeline.skops)
    P->>M: log_artifact(model/pipeline.skops)
    P->>M: log_dict(model/signature.json)  (infer_signature)
    P->>M: set_tags(model_registry, quality_gate)
    P->>M: end_run
    alt r2 >= min_r2 (0.40)
        P-->>DS: exit 0 + summary JSON
    else r2 < min_r2
        P-->>DS: exit 2 (quality gate FAILED)
    end
    Note over P: If M unreachable and --allow-fallback → retry against sqlite:////tmp/mlflow.db
```

**Exit codes:** `0` pass · `1` infra/error · `2` quality gate fail.

---

## 2. Export (sign + promote)

```mermaid
sequenceDiagram
    autonumber
    participant E as pipelines.export
    participant M as MLflow Client
    participant FS as artifacts/
    participant LINK as artifacts/latest (symlink)

    E->>M: get_experiment_by_name(supervised-regression)
    E->>M: search_runs(order_by=start_time DESC, max 1)
    E->>M: download_artifacts(run_id, model/pipeline.skops)
    E->>FS: stage artifacts/<run-id[:12]>/
    E->>E: sha256_of(pipeline.skops)
    E->>FS: write manifest.json {run_id, metrics, params, sha256}
    E->>FS: symlink_to(versioned_dir) as tmp (.latest-<pid>)
    E->>FS: tmp.replace(latest)   (atomic swap)
    E-->>FS: promotion complete
```

**Property:** the `latest` symlink swap is atomic-ish on POSIX, so a serving
process mounted at `artifacts/latest` never reads a half-written target.

---

## 3. Serving API — Startup & Readiness

```mermaid
sequenceDiagram
    autonumber
    participant K as Scheduler/Orchestrator
    participant A as FastAPI (lifespan)
    participant R as ModelRuntime
    participant FS as Artifact mount (read-only)
    participant S as skops

    K->>A: start container (MODEL_ARTIFACT_PATH=/models/latest/pipeline.skops)
    A->>R: resolve_model_path()
    A->>R: ModelRuntime.load(path)
    R->>FS: read manifest.json
    alt manifest has sha256
        R->>FS: stream-hash pipeline.skops
        R-->>FS: actual == expected ?
    end
    R->>S: skio.load(path, trusted=_TRUSTED_TYPES)
    R->>R: _warmup(): predict(zeros(1,3))
    R->>A: set_runtime(runtime)
    A-->>K: readiness /ready → 200 ok (model_version)
    Note over K,A: Missing artifact → app boots, /ready → 503, /health → not-ready
```

---

## 4. Online Prediction

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant A as FastAPI
    participant R as ModelRuntime
    participant M as Metrics (prometheus)
    participant L as structlog

    C->>A: POST /predict {"records":[...]} (X-Request-ID optional)
    A->>A: middleware assigns/propagates X-Request-ID
    A->>A: Pydantic validate (PredictionRequest, extra=forbid, strict)
    alt invalid
        A-->>C: 422 Validation error
    end
    A->>R: get_runtime()
    alt not loaded
        A-->>C: 503 Model not loaded
    end
    R->>R: records_to_matrix(records) → float64 (contract order)
    R->>R: predict(matrix)  (pure in-memory)
    M->>M: model_predictions_total + batch_size hist + inference_seconds hist
    L->>L: predict_served {batch_size, model_version, inference_ms}
    A-->>C: 200 {predictions, model_version, count} + X-Request-ID
```

---

## 5. Observability

```mermaid
sequenceDiagram
    autonumber
    participant A as API (/metrics)
    participant P as Prometheus
    participant D as Dashboards/Alerting

    loop every 15s
        P->>A: GET /metrics (prometheus.yml scrape target api:8000)
        A-->>P: HTTP + business metrics (prometheus_client format)
    end
    P-->>D: aggregate (api latency, predictions_total, ready state)
    Note over D: Alert on readiness degradation + error rate (see observability)
```

**Per-route HTTP metrics** come from `prometheus-fastapi-instrumentator`
(status-code grouped); **business metrics** from `prometheus_client`
(`model_predictions_total`, `model_prediction_batch_size`,
`model_inference_seconds`).

---
*Next: [Data Contracts](data-contracts.md)*