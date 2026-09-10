"""Monorepo smoke tests: schemas, training, and API contract."""

from __future__ import annotations

import numpy as np
import pytest
from common_lib.schemas import FeatureRecord, PredictionRequest
from pipelines.model import as_matrix, build_pipeline


def test_feature_order_stable() -> None:
    assert FeatureRecord.FEATURE_ORDER == ("med_inc", "house_age", "avg_occupancy")


def test_pipeline_fit_predict() -> None:
    rng = np.random.default_rng(42)
    x = rng.normal(size=(200, 3))
    y = x @ np.array([1.0, -2.0, 0.5]) + 0.1 * rng.normal(size=200)
    pipeline = build_pipeline(alpha=1.0)
    pipeline.fit(x, y)
    preds = pipeline.predict(x[:5])
    assert preds.shape == (5,)


def test_as_matrix_column_order() -> None:
    records = [
        {"med_inc": 1.0, "house_age": 2.0, "avg_occupancy": 3.0},
        {"med_inc": 4.0, "house_age": 5.0, "avg_occupancy": 6.0},
    ]
    matrix = as_matrix(records)
    assert matrix.shape == (2, 3)
    np.testing.assert_allclose(matrix, [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])


def test_request_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        PredictionRequest(
            records=[FeatureRecord(med_inc=1000.0, house_age=41.0, avg_occupancy=6.98)]
        )
