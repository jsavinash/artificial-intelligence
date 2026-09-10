"""Export the locally-registered MLflow model artifact to a serving directory.

Usage::

    uv run --package pipelines python -m pipelines.export --out artifacts

Stages ``artifacts/<run-id>/pipeline.skops`` with a signed manifest
(SHA-256, metrics, params) and promotes it via an ``artifacts/latest``
symlink that the serving layer (or Docker bind-mount) can consume.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Final

import mlflow
from common_lib.logging import configure_logging, get_logger
from mlflow.tracking import MlflowClient

logger = get_logger(service="pipelines.export")
ARTIFACT_REL_PATH: Final[str] = "model/pipeline.skops"


def sha256_of(path: Path) -> str:
    """Streaming SHA-256 hex digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 256), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export(
    tracking_uri: str, out_dir: Path, experiment_name: str = "supervised-regression"
) -> Path:
    """Download the latest run's skops pipeline, sign it, and promote it."""
    configure_logging(service="pipelines.export")
    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient(tracking_uri=tracking_uri)

    experiment = client.get_experiment_by_name(experiment_name)
    if experiment is None:
        raise RuntimeError(f"Experiment '{experiment_name}' not found at {tracking_uri}.")
    runs = client.search_runs(
        [experiment.experiment_id], order_by=["attributes.start_time DESC"], max_results=1
    )
    if not runs:
        raise RuntimeError("No runs found in experiment.")

    run = runs[0]
    run_id: str = str(run.info.run_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    downloaded = Path(str(client.download_artifacts(run_id, ARTIFACT_REL_PATH, str(out_dir))))

    versioned_dir = out_dir / run_id[:12]
    versioned_dir.mkdir(parents=True, exist_ok=True)
    target = versioned_dir / Path(ARTIFACT_REL_PATH).name
    Path(downloaded).replace(target)

    manifest: dict[str, Any] = {
        "run_id": run_id,
        "experiment_id": run.info.experiment_id,
        "metrics": dict(run.data.metrics),
        "params": dict(run.data.params),
        "artifact": target.name,
        "sha256": sha256_of(target),
    }
    (versioned_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # Promote: artifacts/latest -> <run-id> (atomic-ish symlink swap).
    latest_link = out_dir / "latest"
    tmp_link = out_dir / f".latest-{os.getpid()}"
    if tmp_link.is_symlink() or tmp_link.exists():
        tmp_link.unlink()
    tmp_link.symlink_to(versioned_dir.name)
    tmp_link.replace(latest_link)

    logger.info(
        "model_exported",
        run_id=manifest["run_id"],
        artifact=str(target),
        sha256=manifest["sha256"][:16],
    )
    return versioned_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Export serving artifact from MLflow.")
    parser.add_argument("--tracking-uri", default="http://localhost:5000")
    parser.add_argument("--out", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    export(args.tracking_uri, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
