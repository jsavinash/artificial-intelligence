# Data Contracts

The **single source of truth** for every schema is
`libs/common/src/common_lib/schemas.py`. This page documents the external
contract strictly and warns against drift. Any change to the contract **must**
change the source file (not this doc) and be reflected here.

## Design principles

1. **One canonical feature contract** shared by training and serving — the
   anti-train/serve-skew guarantee.
2. **Strict by default:** `extra="forbid"` rejects unknown fields; strict
   float/int types prohibit string coercion; bounds and finiteness enforced.
3. **Documented ranges** so clients and the training pipeline agree.
4. **Order == contract:** `FeatureRecord.FEATURE_ORDER` defines column order;
   both `records_to_matrix()` (API) and `as_matrix()`/model (training) derive
   from it — the order can never silently drift.

---

## 1. `FeatureRecord` — one feature vector

| Field | Type | Bounds | Meaning | Example |
|---|---|---|---|---|
| `med_inc` | float (strict) | `0.0 ≤ v ≤ 100.0` | Median income in block group (10k USD units) | `8.3252` |
| `house_age` | float (strict) | `0.0 ≤ v ≤ 100.0` | Median house age (years) | `41.0` |
| `avg_occupancy` | float (strict) | `v > 0.0` | Average household occupancy | `6.98` |

- `model_config = ConfigDict(frozen=True, extra="forbid")`
- **Finiteness:** every value must be finite — `NaN`/`±Inf` rejected.
- **Order:** `FEATURE_ORDER = ("med_inc", "house_age", "avg_occupancy")`.

---

## 2. `PredictionRequest` — request envelope

```json
{
  "records": [
    {"med_inc": 8.3252, "house_age": 41.0, "avg_occupancy": 6.98}
  ]
}
```

- `records`: `list[FeatureRecord]`
- **Constraints:** `min_length=1`, `max_length=1024` (memory/latency guard).
- `extra="forbid"` at the request level too.

---

## 3. `PredictionResponse` — response envelope

```json
{
  "predictions": [4.9871, 4.9912],
  "model_version": "abcdef123456",
  "count": 2
}
```

- `predictions`: `list[float]` (`min_length=1`)
- `model_version`: str — run_id prefix from the served manifest
- `count`: strict int — **validated** to equal `len(predictions)`

---

## 4. `HealthResponse` — liveness/readiness payload

```json
{
  "status": "ok",              // "ok" | "degraded" | "not-ready"
  "model_loaded": true,
  "model_version": "abcdef123456"  // null when not loaded
}
```

---

## 5. HTTP-level contract

| Method | Path | Success | Failure |
|---|---|---|---|
| `GET` | `/health` | 200 — liveness (`ok`/`degraded`/`not-ready`) | — |
| `GET` | `/ready` | 200 `ok` | 503 when not loaded |
| `POST` | `/predict` | 200 prediction | 422 validation · 503 not loaded |
| `GET` | `/metrics` | 200 Prometheus text | — (excluded from HTTP instrumentator) |

**Tracing header:** `X-Request-ID` is propagated if present, else a `uuid4`
hex string is assigned; echoed back on every response. This ties logs and
metrics to a single request across hops.

---

## 6. Artifact contract (manifest.json)

Written by `pipelines.export`, verified by `api.runtime` at load:

```json
{
  "run_id": "3f3c1afd3e6c...",
  "experiment_id": "1",
  "metrics": {"rmse": 0.62, "mae": 0.44, "r2": 0.81},
  "params": {"model_type": "Ridge", "alpha": 1.0, "feature_names": "med_inc,house_age,avg_occupancy"},
  "artifact": "pipeline.skops",
  "sha256": "9f86d081884c7d65..."
}
```

- `sha256` is a **streaming SHA-256** of the artifact computed at export time.
- At load, the API recomputes and refuses mismatches
  (`ArtifactIntegrityError`).
- Serialization is **skops** with a trusted-type allow-list
  (`_TRUSTED_TYPES`): `StandardScaler`, `Ridge`, `numpy.dtype`. Unknown types
  are not deserialized (security).

---

## 7. Versioning & compatibility

| Change | Type | Impact | Required action |
|---|---|---|---|
| Add field (backwards-compatible) | Minor | Non-breaking | Keep `extra="forbid"`; add optional w/ default; bump contract doc |
| Remove/rename field or reorder `FEATURE_ORDER` | Breaking | Retrain + new artifact; both sides must deploy together | New ADR + coordinated release |
| Relax bounds | Minor | Client-ok | Verify serving bounds vs training data range |
| Tighten bounds | Breaking | May 422 previously-valid input | Communicate to clients |

> **Rule:** `FEATURE_ORDER` and the pipeline in `model.py` must change
> together, and the artifact must be retrained and re-exported in the same
> release. The API warmup predict (`zeros(1,3)`) enforces this at boot.

---
*Next: [Architecture Decision Records](adr/README.md)*