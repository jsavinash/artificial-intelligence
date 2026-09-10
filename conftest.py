"""Shared fixtures: a tiny trained artifact with signed manifest for API tests."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
import skops.io as skio
from pipelines.model import build_pipeline


def _make_artifact(dir_path: Path) -> Path:
    """Fit a 3-feature pipeline on synthetic data and stage it with a manifest."""
    rng = np.random.default_rng(7)
    x = rng.normal(size=(100, 3))
    y = x @ np.array([2.0, -1.0, 0.5]) + 0.05 * rng.normal(size=100)
    pipeline = build_pipeline(alpha=0.1)
    pipeline.fit(x, y)

    artifact = dir_path / "pipeline.skops"
    skio.dump(pipeline, artifact)
    manifest = {
        "run_id": "abcdef1234567890" + "0" * 16,
        "metrics": {"r2": 0.99, "rmse": 0.05},
        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
    }
    (dir_path / "manifest.json").write_text(json.dumps(manifest))
    return artifact


@pytest.fixture()
def model_artifact(tmp_path: Path) -> Path:
    artifact_dir = tmp_path / "abc123456789"
    artifact_dir.mkdir(parents=True)
    return _make_artifact(artifact_dir)


@pytest.fixture()
def api_client(model_artifact: Path) -> Iterator[object]:
    """TestClient with lifespan executed against a real artifact."""
    os.environ["MODEL_ARTIFACT_PATH"] = str(model_artifact)
    from api.main import app
    from api.runtime import reset_runtime
    from fastapi.testclient import TestClient

    reset_runtime()
    with TestClient(app) as client:
        yield client
    reset_runtime()
