# ML Platform — Supervised Regression Monorepo

Enterprise MLOps monorepo (uv workspace, Python 3.12) for a supervised linear
regression model: shared Pydantic contracts, MLflow-tracked quality-gated
training, and a low-latency FastAPI serving layer with Prometheus
observability and SHA-256-verified model artifacts.

**Status:** 26 tests passing (99% line coverage) · `ruff` + `ruff format` clean ·
`mypy --strict` clean · warnings-as-errors enabled · live serving verified.

## Layout

```
├── pyproject.toml            # uv workspace root (virtual pkg), lint/type/pytest config
├── conftest.py               # shared fixtures: trained artifact + manifest for tests
├── uv.lock                   # frozen, reproducible lockfile
├── settings.toml             # Dynaconf layered config (APP_* env vars override)
├── libs/common/              # Pydantic v2 schemas, structlog JSON logging, Dynaconf config
├── apps/pipelines/           # sklearn Pipeline + Ridge, MLflow tracking, signed export
├── apps/api/                 # FastAPI serving app (lifespan load, /health /ready /predict)
├── infrastructure/           # Multi-stage Dockerfile, docker-compose, prometheus.yml
├── .github/workflows/ci.yml  # lint → types → tests → train → build → live smoke test
└── artifacts/                # <run-id>/pipeline.skops + manifest.json + latest symlink
```

## Quickstart

```bash
make install        # sync all workspace packages (frozen lockfile)
make test           # 26 tests, ~1s
make all            # install → train → export → serve
```

Or run each lifecycle step manually:

```bash
# Train (exits 2 if test R² falls below --min-r2; use --allow-fallback
# to retry against a local sqlite store if the tracking server is down)
uv run --package pipelines python -m pipelines.train \
    --alpha 1.0 --tracking-uri http://localhost:5000

# Export signed artifact (SHA-256 manifest) and promote artifacts/latest symlink
uv run --package pipelines python -m pipelines.export \
    --tracking-uri http://localhost:5000 --out artifacts

# Serve
MODEL_ARTIFACT_PATH=artifacts/latest/pipeline.skops \
    uv run --package api uvicorn api.main:app --port 8000
```

The same steps via make (with overridable variables):

```bash
make train-local ALPHA=1.0 MIN_R2=0.40   # train, sqlite fallback, no server needed
make export TRACKING_URI=http://localhost:5000
make serve PORT=8000                     # dev server (--reload)
make smoke PORT=8000                     # verify /ready, /predict, /metrics
```

## Local stack (API + MLflow + Prometheus)

```bash
make stack-up        # build + start API, MLflow, Prometheus (detached)
make smoke           # verify the API once it is up
make stack-logs      # tail logs
make stack-down      # stop (keep volumes)
make stack-nuke      # stop AND delete volumes (destroys MLflow data)
# API:        http://localhost:8000  (POST /predict, GET /health, GET /ready)
# MLflow UI:  http://localhost:5000
# Prometheus: http://localhost:9090 (scrapes api:8000/metrics every 15s)
```

All three services have healthchecks; the API mounts `../artifacts` read-only
with `no-new-privileges` and CPU/memory limits.

## Docker (single container)

```bash
make docker-build                 # multi-stage image (IMAGE=ml-platform/api:local)
make docker-run PORT=8000         # run container (expects artifacts/ present)
make smoke PORT=8000              # verify
make docker-stop                  # stop + remove container
```

## API

| Endpoint | Purpose | Semantics |
|---|---|---|
| `POST /predict` | Batch inference | 200 · 422 validation · 503 model not loaded |
| `GET /health` | Liveness probe | Always 200 while the process is up |
| `GET /ready` | Readiness probe | 200 only after model load + integrity check + warmup; else 503 |
| `GET /metrics` | Prometheus exposition | HTTP + business metrics |

`POST /predict` request body:

```json
{"records": [{"med_inc": 8.33, "house_age": 41.0, "avg_occupancy": 6.98}]}
```

Strict validation: bounded batch size (≤1024), strict floats (no string
coercion), finite-value checks, `extra="forbid"`, frozen models, `count`
cross-validated against the predictions. Every response carries an
`X-Request-ID` (propagated or assigned).

**Metrics:** per-route HTTP counts and latency histograms, plus business
metrics — `model_predictions_total` (labelled by model version),
`model_prediction_batch_size`, and `model_inference_seconds` (pure
`pipeline.predict` time, excluding HTTP overhead).

## Model lifecycle

1. **Train** (`pipelines.train`) — California Housing restricted to the exact
   served feature contract; fixed seed; params, metrics, and the skops
   artifact logged to MLflow; input signature logged as
   `model/signature.json`; quality gate tagged on the run.
2. **Export** (`pipelines.export`) — downloads the latest run's artifact,
   stages `artifacts/<run-id>/` with a signed `manifest.json` (SHA-256,
   metrics, params), and promotes the `artifacts/latest` symlink atomically.
3. **Serve** (`api.runtime`) — load-time SHA-256 verification against the
   manifest, trusted-type skops deserialization, a warmup predict on
   contract-shaped input (a mismatched artifact fails to boot), then pure
   in-memory inference.

## Reproducibility & rigor

- Single canonical feature contract (`common_lib.schemas.FeatureRecord`) used
  by *both* training and serving — no train/serve skew, enforced at load time.
- Deterministic seed; every hyperparameter, metric, and artifact logged to
  MLflow; run-id lineage surfaces in `/health` and `/ready` responses.
- Quality gate: training exits non-zero if test R² falls below `--min-r2`
  (default 0.40).
- Artifact serialized with `skops` (secure, version-safe) and SHA-256-verified
  against its signed manifest at load time.
- Docker image: multi-stage, non-root (uid 10001), HEALTHCHECK, wheels built
  with `--no-editable` (no builder-stage paths leak into the runtime image).
- CI: ruff + ruff format + `mypy --strict` + pip-audit + pytest coverage gate
  (`--cov-fail-under=70`), followed by a docker build with a live serving
  smoke test (readiness, prediction, non-root assertion).

## Development

All operations are available as make targets — run `make help` for the full
auto-generated list:

| Area | Targets |
|---|---|
| Quality gates | `check` (all of the below), `lint`, `format`, `format-check`, `typecheck`, `test`, `test-cov`, `audit` |
| Environment | `install`, `install-frozen`, `lock`, `upgrade` |
| Model lifecycle | `train`, `train-local`, `export`, `serve`, `serve-prod` |
| Verification | `smoke` (`PORT=...`) |
| Docker | `docker-build`, `docker-run`, `docker-stop`, `stack-up`, `stack-down`, `stack-nuke`, `stack-logs` |
| Cleanup | `clean`, `clean-artifacts`, `clean-all` |
| Composite | `check`, `ci` (gates + docker build), `all` (install → train → export → serve) |

Overridable variables (all have sensible defaults): `PORT`, `ALPHA`,
`MIN_R2`, `TRACKING_URI`, `MODEL_PATH`, `ARTIFACTS_DIR`, `IMAGE`.
For example: `make train ALPHA=0.5 MIN_R2=0.5` or `make smoke PORT=9000`.

Equivalent raw commands (what the make targets wrap):

```bash
uv run ruff check .          # lint
uv run ruff format .         # format
uv run mypy libs apps        # strict type check
uv run pytest                # tests (warnings = errors)
uv run pytest --cov          # with coverage report
```

Tests run in ~1s with no network: the API suite uses `TestClient` against a
tiny synthetic artifact (built in `conftest.py`) — covering the full load →
verify → warmup → serve path. One documented upstream ignore remains in
`filterwarnings` (starlette's anyio deprecation); remove it when starlette
updates.
