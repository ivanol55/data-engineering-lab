"""Train the login-risk model and record the run in MLflow.

Usage:
    python ml/train.py
"""

from __future__ import annotations

import json
import os
import pickle
import sys
from pathlib import Path

import mlflow
import mlflow.sklearn
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml import config, features  # noqa: E402


def _metrics(y_true, y_pred, y_score) -> dict[str, float]:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_score)),
    }


def main() -> int:
    train, test = features.dataset()
    if train.empty or test.empty:
        raise SystemExit(
            "the split produced an empty side; check SPLIT_STRATEGY and TEST_DAYS"
        )

    X_train = train[features.FEATURE_COLUMNS]
    y_train = train["is_attack"]
    X_test = test[features.FEATURE_COLUMNS]
    y_test = test["is_attack"]

    model = Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=config.RANDOM_SEED,
                ),
            ),
        ]
    )
    model.fit(X_train, y_train)

    probabilities = model.predict_proba(X_test)[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    metrics = _metrics(y_test, predictions, probabilities)

    # A rule baseline the model must beat to be worth promoting. The module 7
    # rules are more complex; this is the simplest comparable score.
    baseline_predictions = (X_test["risk_score"] >= 70).astype(int)
    baseline_metrics = _metrics(y_test, baseline_predictions, X_test["risk_score"])

    params = {
        "split_strategy": config.SPLIT_STRATEGY,
        "include_current_event": str(config.INCLUDE_CURRENT_EVENT),
        "test_days": config.TEST_DAYS,
        "seed": config.RANDOM_SEED,
        "model": "logistic_regression",
        "features": ",".join(features.FEATURE_COLUMNS),
        "train_start": str(train["event_time"].min()),
        "train_end": str(train["event_time"].max()),
        "test_start": str(test["event_time"].min()),
        "test_end": str(test["event_time"].max()),
        "train_rows": len(train),
        "test_rows": len(test),
    }

    run_id = None
    if config.LOG_TO_MLFLOW:
        mlflow.set_tracking_uri(
            os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
        )
        mlflow.set_experiment(config.EXPERIMENT_NAME)
        with mlflow.start_run(run_name="logistic-baseline") as run:
            mlflow.log_params(params)
            mlflow.log_metrics(metrics)
            mlflow.log_metrics(
                {f"baseline_{name}": value for name, value in baseline_metrics.items()}
            )
            mlflow.log_dict(
                {
                    "features": features.FEATURE_COLUMNS,
                    "train": params["train_start"] + ".." + params["train_end"],
                    "test": params["test_start"] + ".." + params["test_end"],
                },
                "contract.json",
            )
            mlflow.sklearn.log_model(
                model,
                name="model",
                registered_model_name=(
                    config.MODEL_NAME if config.REGISTER_MODEL else None
                ),
            )
            run_id = run.info.run_id

    Path(config.MODEL_PATH).parent.mkdir(parents=True, exist_ok=True)
    with Path(config.MODEL_PATH).open("wb") as handle:
        pickle.dump(model, handle)

    summary = {
        "run_id": run_id,
        "metrics": metrics,
        "baseline": baseline_metrics,
        "params": params,
        "features": features.FEATURE_COLUMNS,
    }
    Path(config.RUN_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(config.RUN_PATH).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
