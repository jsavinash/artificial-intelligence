"""Canonical data contracts shared by training and serving.

Single source of truth: the API request/response models and the MLflow
artifact signature are both derived from these types, preventing
train/serve skew.
"""

from __future__ import annotations

import math
from typing import ClassVar, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    field_validator,
    model_validator,
)

HealthStatus = Literal["ok", "degraded", "not-ready"]


class FeatureRecord(BaseModel):
    """One regression feature vector. Field order matches the trained pipeline."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    med_inc: StrictFloat = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Median income in block group (10k USD units).",
        examples=[8.3252],
    )
    house_age: StrictFloat = Field(
        ..., ge=0.0, le=100.0, description="Median house age (years).", examples=[41.0]
    )
    avg_occupancy: StrictFloat = Field(
        ..., gt=0.0, description="Average household occupancy.", examples=[6.98]
    )

    FEATURE_ORDER: ClassVar[tuple[str, ...]] = (
        "med_inc",
        "house_age",
        "avg_occupancy",
    )

    @field_validator("med_inc", "house_age", "avg_occupancy")
    @classmethod
    def reject_non_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Feature values must be finite (no NaN/inf).")
        return value


class PredictionRequest(BaseModel):
    """Batch prediction envelope — bounded to protect memory and latency."""

    model_config = ConfigDict(extra="forbid")

    records: list[FeatureRecord] = Field(..., min_length=1, max_length=1024)


class PredictionResponse(BaseModel):
    """Batch prediction result with per-record outputs and trace metadata."""

    model_config = ConfigDict(frozen=True)

    predictions: list[float] = Field(..., min_length=1)
    model_version: str
    count: StrictInt

    @model_validator(mode="after")
    def count_matches_predictions(self) -> PredictionResponse:
        if self.count != len(self.predictions):
            raise ValueError("`count` must equal the number of predictions.")
        return self


class HealthResponse(BaseModel):
    """Liveness/readiness probe payload."""

    model_config = ConfigDict(frozen=True)

    status: HealthStatus = "ok"
    model_loaded: bool
    model_version: str | None = None
