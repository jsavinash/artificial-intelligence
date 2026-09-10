# Testing Strategy

Maps the test suite to the risk it mitigates and documents the CI harness.
Tests run fast (~1s) and **offline** — the API suite builds a tiny synthetic
artifact in `conftest.py` and drives the full load → verify → warmup → serve
path via FastAPI `TestClient`.

## 1. Test pyramid (current)

```
        E2E / smoke   (CI live container: ready + predict + non-root)
        -------------
      Integration      (API TestClient over real artifact; lifecycle)
        -------------
      Unit             (schemas, runtime integrity, logging, pipeline)
        -------------
```

| Layer | Location | Coverage of risk |
|---|---|---|
| Unit | `tests/` + app tests | Schemas, contract, runtime integrity, logging/config |
| Integration | `apps/api/tests/test_api.py` | HTTP contract, validation, 503 paths, metrics |
| E2E/System | CI `docker-build` smoke + `make smoke` | Real image: readiness, predict, non-root |

## 2. What the suite verifies

- **Contract / validation:** range bounds, finiteness, `extra="forbid"`,
  strict-float rejection of string coercion, empty batch rejection
  (`test_api.py`, `test_smoke.py`).
- **Determinism/order:** `FEATURE_ORDER` stability; column order via
  `as_matrix`/`records_to_matrix`; order-independence of batch predictions.
- **Artifact integrity:** SHA-256 verification (corrupted artifact →
  `ArtifactIntegrityError`), corrupt manifest → `ArtifactIntegrityError`,
  fallback versioning without manifest, **warmup shape mismatch** on a 5-feature
  artifact (`test_runtime.py`).
- **Startup/failure semantics:** missing artifact → `not-ready`, `/ready` 503,
  `/predict` 503 (`test_not_ready_returns_503`).
- **Readiness/health contract** and `X-Request-ID` round-trip.
- **Metrics** exposure (`model_predictions_total`,
  `model_prediction_batch_size`, `model_inference_seconds`).
- **Logging:** JSON record shape (`service`, `level`, `timestamp`), settings
  layering + env override + missing-file tolerance (`test_logging_config.py`).

## 3. CI harness

`make check` = lint + format-check + typecheck + test (CI parity); CI adds
`--cov --cov-fail-under=70` and `pip-audit`.

- **Warnings are errors:** `filterwarnings = ["error", ...]`.
- One documented upstream ignore for starlette/anyio deprecation; remove when
  starlette updates.
- Coverage floor **70%** enforced in CI (`--cov-fail-under=70`).

## 4. Fixtures

`conftest.py`:
- `model_artifact`: fits a 3-feature Ridge on synthetic data, writes
  `pipeline.skops` + `manifest.json` (with computed SHA-256 and fixed
  `run_id` `abcdef123456…`) → drives runtime + API tests.
- `api_client`: sets `MODEL_ARTIFACT_PATH`, resets runtime, wraps `TestClient`
  so `lifespan` runs against the real artifact.

## 5. Gaps & recommended additions

| Gap | Priority | Suggestion |
|---|---|---|
| Performance/load budgets | High | k6/locust; assert p99 inference + throughput |
| Property/fuzz testing | Medium | `hypothesis` strategies over `FeatureRecord` |
| Concurrency/parallel requests | Medium | Test two uvicorn workers / concurrent `/predict` |
| Security-focused tests | Medium | Very large/`NaN`/path-traversal-tolerant input; authorization tests once gateway added |
| Mutation/regression for manifest parsing | Low | Table-driven corrupt-manifest cases |

## 6. Running the suite

```bash
make test            # pytest (warnings = errors)
make test-cov        # coverage + term-missing
make check           # lint + format + typecheck + test
make ci              # check + docker build/smoke
```

---
*Back: [Architecture index](README.md)*