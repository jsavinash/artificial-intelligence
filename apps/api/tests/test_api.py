"""API contract tests: health, readiness, prediction, validation, metrics."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def test_health_ready(api_client: Any) -> None:
    response = api_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True
    assert body["model_version"] == "abcdef123456"  # run_id[:12] from manifest


def test_ready_endpoint(api_client: Any) -> None:
    response = api_client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_predict_happy_path(api_client: Any) -> None:
    response = api_client.post(
        "/predict",
        json={"records": [{"med_inc": 8.3, "house_age": 41.0, "avg_occupancy": 6.98}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert len(body["predictions"]) == 1
    assert isinstance(body["predictions"][0], float)
    assert body["model_version"] == "abcdef123456"


def test_predict_batch_order_independent(api_client: Any) -> None:
    record = {"med_inc": 8.3, "house_age": 41.0, "avg_occupancy": 6.98}
    single = api_client.post("/predict", json={"records": [record]}).json()["predictions"][0]
    batch = api_client.post("/predict", json={"records": [record, record]}).json()
    assert batch["count"] == 2
    assert batch["predictions"][0] == single == batch["predictions"][1]


def test_predict_rejects_out_of_range(api_client: Any) -> None:
    response = api_client.post(
        "/predict",
        json={"records": [{"med_inc": -5.0, "house_age": 41.0, "avg_occupancy": 6.98}]},
    )
    assert response.status_code == 422


def test_predict_rejects_extra_fields(api_client: Any) -> None:
    response = api_client.post(
        "/predict",
        json={"records": [{"med_inc": 1.0, "house_age": 2.0, "avg_occupancy": 3.0, "extra": 1}]},
    )
    assert response.status_code == 422


def test_predict_rejects_empty_batch(api_client: Any) -> None:
    response = api_client.post("/predict", json={"records": []})
    assert response.status_code == 422


def test_predict_rejects_string_numbers(api_client: Any) -> None:
    response = api_client.post(
        "/predict",
        json={"records": [{"med_inc": "8.3", "house_age": 41.0, "avg_occupancy": 6.98}]},
    )
    assert response.status_code == 422  # StrictFloat: no string coercion


def test_request_id_header_roundtrip(api_client: Any) -> None:
    response = api_client.get("/health", headers={"X-Request-ID": "trace-123"})
    assert response.headers["X-Request-ID"] == "trace-123"
    assigned = api_client.get("/health")
    assert len(assigned.headers["X-Request-ID"]) == 32  # uuid4 hex


def test_not_ready_returns_503(tmp_path: Path, monkeypatch: Any) -> None:
    """Missing artifact: app boots degraded; /ready 503; /predict 503."""

    monkeypatch.setenv("MODEL_ARTIFACT_PATH", str(tmp_path / "does-not-exist.skops"))
    from api.main import app
    from api.runtime import reset_runtime
    from fastapi.testclient import TestClient

    reset_runtime()
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            assert client.get("/health").json()["status"] == "not-ready"
            assert client.get("/ready").status_code == 503
            response = client.post(
                "/predict",
                json={"records": [{"med_inc": 1.0, "house_age": 2.0, "avg_occupancy": 3.0}]},
            )
            assert response.status_code == 503
    finally:
        reset_runtime()


def test_business_metrics_exposed(api_client: Any) -> None:
    api_client.post(
        "/predict",
        json={"records": [{"med_inc": 8.3, "house_age": 41.0, "avg_occupancy": 6.98}]},
    )
    metrics = api_client.get("/metrics").text
    assert "model_predictions_total" in metrics
    assert "model_prediction_batch_size" in metrics
    assert "model_inference_seconds" in metrics
