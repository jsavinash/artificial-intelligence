"""Model runtime tests: manifest verification, integrity, warmup, 503 path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from api.runtime import (
    ArtifactIntegrityError,
    ModelRuntime,
    records_to_matrix,
)
from common_lib.schemas import FeatureRecord
from pipelines.model import build_pipeline


def test_load_with_valid_manifest(model_artifact: Path) -> None:
    runtime = ModelRuntime.load(model_artifact)
    assert runtime.version == "abcdef123456"
    assert runtime.run_id == "abcdef1234567890" + "0" * 16
    assert runtime.training_metrics["r2"] == 0.99
    assert runtime.is_ready()


def test_load_without_manifest_uses_dir_name(tmp_path: Path, model_artifact: Path) -> None:
    bare = tmp_path / "v99"
    bare.mkdir()
    (bare / "pipeline.skops").write_bytes(model_artifact.read_bytes())
    runtime = ModelRuntime.load(bare / "pipeline.skops")
    assert runtime.version == "v99"
    assert runtime.run_id is None


def test_load_rejects_corrupted_artifact(tmp_path: Path, model_artifact: Path) -> None:
    tampered = tmp_path / "bad"
    tampered.mkdir()
    data = bytearray(model_artifact.read_bytes())
    data[len(data) // 2] ^= 0xFF  # flip a byte
    (tampered / "pipeline.skops").write_bytes(bytes(data))
    (tampered / "manifest.json").write_text(
        model_artifact.parent.joinpath("manifest.json").read_text()
    )
    with pytest.raises(ArtifactIntegrityError, match="sha256"):
        ModelRuntime.load(tampered / "pipeline.skops")


def test_load_rejects_corrupt_manifest(tmp_path: Path, model_artifact: Path) -> None:
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "pipeline.skops").write_bytes(model_artifact.read_bytes())
    (broken / "manifest.json").write_text("{not json")
    with pytest.raises(ArtifactIntegrityError, match="Corrupt manifest"):
        ModelRuntime.load(broken / "pipeline.skops")


def test_predict_matches_training_expectation(model_artifact: Path) -> None:
    runtime = ModelRuntime.load(model_artifact)
    # Model approximates y = 2*x0 - x1 + 0.5*x2
    matrix = records_to_matrix([FeatureRecord(med_inc=1.0, house_age=1.0, avg_occupancy=1.0)])
    (prediction,) = runtime.predict(matrix)
    assert prediction == pytest.approx(1.5, abs=0.1)


def test_predict_shape_mismatch_fails_at_load(tmp_path: Path) -> None:
    """An artifact trained on a different feature count must fail warmup."""
    import numpy as np
    import skops.io as skio

    rng = np.random.default_rng(0)
    x = rng.normal(size=(50, 5))  # 5 features ≠ contract's 3
    y = x.sum(axis=1)
    wrong = build_pipeline(alpha=0.1)
    wrong.fit(x, y)
    path = tmp_path / "pipeline.skops"
    skio.dump(wrong, path)
    (tmp_path / "manifest.json").write_text(json.dumps({"run_id": "x" * 32}))
    with pytest.raises(ArtifactIntegrityError, match="Warmup"):
        ModelRuntime.load(path)
