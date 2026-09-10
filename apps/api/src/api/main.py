"""Low-latency serving API for the supervised regression model.

Startup (`lifespan`): load the trained pipeline once into memory.
Endpoints:
    POST /predict  — batched, Pydantic-validated inference
    GET  /health   — liveness (always 200) / readiness (503 until model loads)
    GET  /metrics  — Prometheus exposition (HTTP + inference metrics)
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from common_lib.logging import configure_logging, get_logger
from common_lib.schemas import (
    HealthResponse,
    PredictionRequest,
    PredictionResponse,
)
from fastapi import FastAPI, HTTPException, Request, Response, status
from prometheus_client import Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

from api.runtime import (
    ModelNotLoadedError,
    ModelRuntime,
    get_runtime,
    records_to_matrix,
    resolve_model_path,
    set_runtime,
)

logger = get_logger(service="api")

# --- Business metrics (in addition to per-route HTTP metrics) ---------------
PREDICTIONS_TOTAL = Counter(
    "model_predictions_total",
    "Individual predictions served.",
    ["model_version"],
)
PREDICTION_BATCH_SIZE = Histogram(
    "model_prediction_batch_size",
    "Number of records per /predict batch.",
    buckets=(1, 2, 5, 10, 32, 64, 128, 256, 512, 1024),
)
INFERENCE_SECONDS = Histogram(
    "model_inference_seconds",
    "Time spent in model.predict() only (excludes HTTP overhead).",
    buckets=(0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5),
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load the model artifact at startup; fail fast if unavailable."""
    configure_logging(service="api", level="INFO")
    path: Path = resolve_model_path()
    try:
        runtime = ModelRuntime.load(path)
        set_runtime(runtime)
        logger.info("startup_complete", model_version=runtime.version)
    except FileNotFoundError:
        logger.error("model_artifact_missing", path=str(path))
        # App still boots so readiness probes fail loudly (503) until fixed.
    yield
    logger.info("shutdown_complete")


app = FastAPI(
    title="Regression Serving API",
    version="1.0.0",
    description="Low-latency batch inference for the housing regression pipeline.",
    lifespan=lifespan,
)

# --- Observability middleware ------------------------------------------------


@app.middleware("http")
async def request_id_header(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Propagate/assign X-Request-ID for end-to-end tracing."""
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


instrumentator = Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    excluded_handlers=["/health", "/metrics"],
)
instrumentator.instrument(app).expose(app, include_in_schema=False, endpoint="/metrics")


# --- Endpoints ---------------------------------------------------------------


@app.get("/health", response_model=HealthResponse, tags=["ops"], summary="Liveness probe")
def health() -> HealthResponse:
    """Liveness: always 200 while the process is up (k8s livenessProbe)."""
    try:
        runtime = get_runtime()
        return HealthResponse(
            status="ok" if runtime.is_ready() else "degraded",
            model_loaded=runtime.is_ready(),
            model_version=runtime.version,
        )
    except ModelNotLoadedError:
        return HealthResponse(status="not-ready", model_loaded=False, model_version=None)


@app.get("/ready", response_model=HealthResponse, tags=["ops"], summary="Readiness probe")
def ready() -> HealthResponse:
    """Readiness: 503 until the model is loaded and warm (k8s readinessProbe)."""
    try:
        runtime = get_runtime()
        if not runtime.is_ready():
            raise ModelNotLoadedError("model degraded")
        return HealthResponse(status="ok", model_loaded=True, model_version=runtime.version)
    except ModelNotLoadedError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not loaded",
        ) from None


@app.post(
    "/predict",
    response_model=PredictionResponse,
    status_code=status.HTTP_200_OK,
    tags=["inference"],
    summary="Batch inference",
    responses={503: {"description": "Model not loaded"}, 422: {"description": "Validation error"}},
)
def predict(payload: PredictionRequest) -> PredictionResponse:
    """Validate the batch, build the feature matrix, and score it in-memory."""
    try:
        runtime = get_runtime()
    except ModelNotLoadedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    matrix = records_to_matrix(payload.records)
    start = time.perf_counter()
    predictions = runtime.predict(matrix)
    elapsed = time.perf_counter() - start

    PREDICTIONS_TOTAL.labels(model_version=runtime.version).inc(len(predictions))
    PREDICTION_BATCH_SIZE.observe(len(predictions))
    INFERENCE_SECONDS.observe(elapsed)

    logger.info(
        "predict_served",
        batch_size=len(predictions),
        model_version=runtime.version,
        inference_ms=round(elapsed * 1000, 3),
    )
    return PredictionResponse(
        predictions=predictions,
        model_version=runtime.version,
        count=len(predictions),
    )
