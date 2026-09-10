"""Training entry point with full MLflow experiment tracking.

Usage (from repo root)::

    uv run --package pipelines python -m pipelines.train --alpha 1.0

Reproducibility: fixed RNG seed, pinned dataset version, every hyperparameter
and metric logged to MLflow; the fitted pipeline is serialized with ``skops``
(version-safe, secure format) and registered as an MLflow artifact.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import mlflow
import numpy as np
import sklearn
import skops.io as skio
from common_lib.logging import configure_logging, get_logger
from mlflow.models import infer_signature
from mlflow.tracking import MlflowClient
from sklearn.datasets import fetch_california_housing
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

from pipelines.model import build_pipeline

logger = get_logger(service="pipelines.train")
RANDOM_SEED: int = 42
MIN_R2_GATE: float = 0.40  # fail the run if the model is worse than this


def load_data() -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Load California Housing restricted to the *served* feature contract.

    Training must use exactly the columns exposed by
    :class:`common_lib.schemas.FeatureRecord` — anything else creates
    train/serve skew.
    """
    from common_lib.schemas import FeatureRecord

    dataset = fetch_california_housing()
    # Contract name -> dataset name (explicit mapping, no fragile name munging).
    mapping = {
        "med_inc": "MedInc",
        "house_age": "HouseAge",
        "avg_occupancy": "AveOccup",
    }
    index_by_name = {name: idx for idx, name in enumerate(dataset.feature_names)}
    selected = [index_by_name[mapping[col]] for col in FeatureRecord.FEATURE_ORDER]
    return dataset.data[:, selected], dataset.target, [dataset.feature_names[i] for i in selected]


def train(alpha: float, tracking_uri: str, min_r2: float = MIN_R2_GATE) -> dict[str, Any]:
    """Run one training job and return the logged run summary."""
    configure_logging(service="pipelines.train")

    x, y, feature_names = load_data()
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.2, random_state=RANDOM_SEED
    )

    pipeline = build_pipeline(alpha=alpha)

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment("supervised-regression")

    with mlflow.start_run(run_name=f"ridge-alpha-{alpha}") as run:
        mlflow.log_params(
            {
                "model_type": "Ridge",
                "alpha": alpha,
                "random_seed": RANDOM_SEED,
                "n_features": x.shape[1],
                "feature_names": ",".join(feature_names),
                "sklearn_version": sklearn.__version__,
            }
        )

        pipeline.fit(x_train, y_train)
        predictions = pipeline.predict(x_test)

        metrics: dict[str, float] = {
            "rmse": float(np.sqrt(mean_squared_error(y_test, predictions))),
            "mae": float(mean_absolute_error(y_test, predictions)),
            "r2": float(r2_score(y_test, predictions)),
        }
        mlflow.log_metrics(metrics)

        # Serialize the *whole* pipeline (scaler + model) with skops.
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path = Path(tmp) / "pipeline.skops"
            skio.dump(pipeline, artifact_path)
            mlflow.log_artifact(str(artifact_path), artifact_path="model")

            # Log the serving input contract alongside the artifact.
            signature = infer_signature(x_test[:8], predictions[:8])
            mlflow.log_dict(signature.to_dict(), "model/signature.json")
            mlflow.set_tags(
                {
                    "model_registry": "housing-regression",
                    "artifact_format": "skops",
                    "quality_gate": "pass" if metrics["r2"] >= min_r2 else "fail",
                }
            )

        client = MlflowClient(tracking_uri=tracking_uri)
        run_info = client.get_run(run.info.run_id)
        summary: dict[str, Any] = {
            "run_id": run.info.run_id,
            "experiment_id": run.info.experiment_id,
            "metrics": metrics,
            "params": run_info.data.params,
            "artifact_uri": run.info.artifact_uri,
            "quality_gate_pass": metrics["r2"] >= min_r2,
        }

    logger.info("training_complete", **summary["metrics"], run_id=summary["run_id"])
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the regression pipeline.")
    parser.add_argument("--alpha", type=float, default=1.0, help="Ridge regularization.")
    parser.add_argument(
        "--tracking-uri", default="http://localhost:5000", help="MLflow tracking server."
    )
    parser.add_argument(
        "--fallback-uri",
        default="sqlite:////tmp/mlflow.db",
        help="Used only with --allow-fallback when the server is unreachable.",
    )
    parser.add_argument(
        "--allow-fallback",
        action="store_true",
        help="Retry training against the fallback URI if the primary fails.",
    )
    parser.add_argument(
        "--min-r2", type=float, default=MIN_R2_GATE, help="Quality gate on test R^2."
    )
    args = parser.parse_args()

    try:
        summary = train(args.alpha, args.tracking_uri, min_r2=args.min_r2)
    except Exception:
        if not args.allow_fallback:
            logger.exception("training_failed", tracking_uri=args.tracking_uri)
            return 1
        logger.exception("training_failed_falling_back", tracking_uri=args.tracking_uri)
        try:
            summary = train(args.alpha, args.fallback_uri, min_r2=args.min_r2)
        except Exception:
            logger.exception("fallback_training_failed", fallback_uri=args.fallback_uri)
            return 1

    print(json.dumps(summary, indent=2))
    return 0 if summary["quality_gate_pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
