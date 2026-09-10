"""Scikit-learn model/pipeline factory.

The *entire* feature transformation and estimator live in one
``sklearn.Pipeline`` so the serialized artifact is self-contained: the API
never reimplements preprocessing, eliminating train/serve skew by design.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt
from common_lib.schemas import FeatureRecord
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def build_pipeline(alpha: float = 1.0) -> Pipeline:
    """Return the canonical regression pipeline: scale -> Ridge."""
    return Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            ("regressor", Ridge(alpha=alpha)),
        ],
        memory=None,
    )


def records_to_matrix(records: list[FeatureRecord]) -> npt.NDArray[np.float64]:
    """Canonical conversion: validated records -> column-ordered float64 matrix.

    Used by BOTH training-side helpers and the serving API so the column
    order can never drift from ``FeatureRecord.FEATURE_ORDER``.
    """
    return np.asarray(
        [[getattr(record, column) for column in FeatureRecord.FEATURE_ORDER] for record in records],
        dtype=np.float64,
    )


def as_matrix(rows: list[dict[str, Any]]) -> npt.NDArray[np.float64]:
    """Convert list-of-dicts into a matrix via the validated contract."""
    return records_to_matrix([FeatureRecord.model_validate(row) for row in rows])
