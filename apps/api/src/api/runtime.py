"""Model runtime: loads the trained artifact once into process memory.

The heavy work (skops deserialization) happens exactly once in the FastAPI
``lifespan`` handler, so per-request latency is pure NumPy inference
(sub-millisecond for this model class). The loader verifies artifact
integrity (SHA-256 against ``manifest.json``) and warms the pipeline with a
single predict so the first real request never pays lazy-init costs.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Final

import numpy as np
import numpy.typing as npt
import skops.io as skio
from common_lib.logging import get_logger
from common_lib.schemas import FeatureRecord
from sklearn.pipeline import Pipeline

logger = get_logger(service="api.runtime")

MODEL_PATH_ENV: Final[str] = "MODEL_ARTIFACT_PATH"
DEFAULT_MODEL_PATH: Final[Path] = Path("/models/pipeline.skops")
MANIFEST_NAME: Final[str] = "manifest.json"
_TRUSTED_TYPES: Final[list[str]] = [
    "sklearn.preprocessing._data.StandardScaler",
    "sklearn.linear_model._ridge.Ridge",
    "numpy.dtype",
]


class ModelNotLoadedError(RuntimeError):
    """Raised when inference is requested before the artifact is available."""


class ArtifactIntegrityError(RuntimeError):
    """Artifact does not match its manifest (corrupted or mismatched)."""


def sha256_of(path: Path) -> str:
    """Streaming SHA-256 hex digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 256), b""):
            digest.update(chunk)
    return digest.hexdigest()


def records_to_matrix(records: list[FeatureRecord]) -> npt.NDArray[np.float64]:
    """Column-ordered matrix in the canonical feature order."""
    return np.asarray(
        [[getattr(record, column) for column in FeatureRecord.FEATURE_ORDER] for record in records],
        dtype=np.float64,
    )


class ModelRuntime:
    """Holds the fitted sklearn pipeline and serves batch inference."""

    def __init__(
        self,
        pipeline: Pipeline,
        version: str,
        run_id: str | None = None,
        training_metrics: dict[str, float] | None = None,
    ) -> None:
        self._pipeline = pipeline
        self._version = version
        self._run_id = run_id
        self._training_metrics = training_metrics or {}

    @classmethod
    def load(cls, path: Path) -> ModelRuntime:
        """Deserialize the artifact, verify integrity, and warm up."""
        logger.info("loading_model", path=str(path))
        manifest = cls._read_manifest(path.parent)
        if manifest is not None:
            expected = manifest.get("sha256")
            if expected is not None:
                actual = sha256_of(path)
                if actual != expected:
                    raise ArtifactIntegrityError(
                        f"Artifact {path} sha256={actual} != manifest {expected}"
                    )
                logger.info("artifact_integrity_verified", sha256=actual[:16])

        pipeline: Pipeline = skio.load(path, trusted=_TRUSTED_TYPES)
        version = manifest.get("run_id", "")[:12] if manifest else (path.parent.name or path.stem)

        runtime = cls(
            pipeline=pipeline,
            version=version,
            run_id=manifest.get("run_id") if manifest else None,
            training_metrics=manifest.get("metrics") if manifest else None,
        )
        runtime._warmup()  # noqa: SLF001 - deliberate private use within class family
        logger.info("model_loaded", path=str(path), version=version)
        return runtime

    @staticmethod
    def _read_manifest(artifact_dir: Path) -> dict[str, Any] | None:
        manifest_path = artifact_dir / MANIFEST_NAME
        if not manifest_path.exists():
            logger.warning("manifest_missing", path=str(manifest_path))
            return None
        try:
            data: dict[str, Any] = json.loads(manifest_path.read_text())
        except json.JSONDecodeError as exc:
            raise ArtifactIntegrityError(f"Corrupt manifest at {manifest_path}") from exc
        # Manifest records a hash of the artifact at export time.
        return data

    def _warmup(self) -> None:
        """One predict on contract-shaped zeros; fails fast on broken artifacts."""
        try:
            self.predict(np.zeros((1, len(FeatureRecord.FEATURE_ORDER)), dtype=np.float64))
        except Exception as exc:
            raise ArtifactIntegrityError(f"Warmup inference failed: {exc}") from exc

    @property
    def version(self) -> str:
        return self._version

    @property
    def run_id(self) -> str | None:
        return self._run_id

    @property
    def training_metrics(self) -> dict[str, float]:
        return dict(self._training_metrics)

    def is_ready(self) -> bool:
        """Readiness: pipeline present and fitted."""
        try:
            return self._pipeline is not None and len(self._pipeline.steps) > 0
        except Exception:  # pragma: no cover - defensive
            return False

    def predict(self, matrix: npt.NDArray[np.float64]) -> list[float]:
        """Batch inference; returns JSON-native floats."""
        output = self._pipeline.predict(matrix)
        return [float(value) for value in output]


_runtime: ModelRuntime | None = None


def set_runtime(runtime: ModelRuntime) -> None:
    global _runtime
    _runtime = runtime


def get_runtime() -> ModelRuntime:
    if _runtime is None:
        raise ModelNotLoadedError("Model not loaded; /health will report not-ready.")
    return _runtime


def reset_runtime() -> None:
    """Test/ops hook: drop the loaded model (next request 503s)."""
    global _runtime
    _runtime = None


def resolve_model_path() -> Path:
    return Path(os.environ.get(MODEL_PATH_ENV, str(DEFAULT_MODEL_PATH)))
