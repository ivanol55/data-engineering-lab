"""Behavioural checks for module 9.

The checks train the learner's pipeline inside the MLflow image, then ask
MLflow what was recorded and read the feature table and the promotion plan.
They do not trust the training script's own printout for anything that can be
queried from the tracking server.
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

ROOT = Path("/workspace")
MLFLOW = "http://mlflow:5000"
MODEL_NAME = "login-risk"
RUN_PATH = Path("/tmp/de-lab-ml/run.json")
PROMOTION = ROOT / "ml" / "promotion.md"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _wait_for_mlflow(timeout: int = 120) -> None:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            response = requests.get(f"{MLFLOW}/health", timeout=2)
            if response.status_code == 200:
                return
            last = f"{response.status_code} {response.text}"
        except requests.RequestException as exc:
            last = str(exc)
        time.sleep(2)
    raise AssertionError(f"MLflow never became ready: {last}")


def _get(path: str, **params) -> dict:
    response = requests.get(f"{MLFLOW}{path}", params=params, timeout=10)
    response.raise_for_status()
    return response.json()


@pytest.fixture(scope="module")
def training() -> dict:
    _wait_for_mlflow()
    if RUN_PATH.exists():
        RUN_PATH.unlink()

    env = dict(os.environ)
    # A one-off container cannot use its own localhost; the service name is
    # the stable address on the Compose network.
    env["MLFLOW_TRACKING_URI"] = MLFLOW
    result = subprocess.run(
        [sys.executable, "ml/train.py"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=900,
    )
    if result.returncode != 0:
        raise AssertionError(
            "ml/train.py failed\n"
            f"--- stdout ---\n{result.stdout[-6000:]}\n"
            f"--- stderr ---\n{result.stderr[-6000:]}"
        )
    if not RUN_PATH.exists():
        raise AssertionError("ml/train.py did not write /tmp/de-lab-ml/run.json")
    summary = json.loads(RUN_PATH.read_text(encoding="utf-8"))
    summary["_stdout"] = result.stdout
    return summary


def test_features_are_point_in_time(training: dict):
    from ml import features

    events = features.load_events()
    built = features.build_features(events)

    assert len(built) == len(events), (
        "the feature table must have exactly one row per event"
    )
    assert built["event_id"].is_unique, "the feature table has duplicate event ids"
    assert "is_attack" not in features.FEATURE_COLUMNS, (
        "the label is a feature; the model is reading the answer"
    )
    assert "outcome" not in features.FEATURE_COLUMNS, (
        "the outcome is a feature; the model is reading the answer"
    )

    expected: dict[str, int] = {}
    for _, group in events.sort_values(["event_time", "event_id"]).groupby(
        "user_id", sort=False
    ):
        failures = 0
        for row in group.itertuples(index=False):
            expected[row.event_id] = failures
            failures += int(row.outcome != "allow")

    observed = dict(zip(built["event_id"], built["prior_failures"]))
    wrong = [
        event_id
        for event_id, prior in expected.items()
        if int(observed[event_id]) != prior
    ]
    assert not wrong, (
        f"{len(wrong)} feature rows count the current event's failure in "
        "`prior_failures`; the model is told the outcome it must predict"
    )


def test_the_holdout_is_later_than_every_training_row(training: dict):
    from ml import features

    params = training["params"]
    assert params["split_strategy"] == "time", (
        "a random split puts future users and campaigns in the training set"
    )

    events = features.load_events()
    last_day = events["event_time"].dt.date.max()

    train_end = params["train_end"]
    test_start = params["test_start"]
    assert train_end < test_start, (
        f"training ends at {train_end} but the holdout starts at {test_start}; "
        "the split is not chronological"
    )
    assert str(last_day) in test_start, (
        f"the holdout does not start on the last fixture day ({last_day}); "
        f"it starts at {test_start}"
    )
    assert params["train_rows"] + params["test_rows"] == len(events), (
        "the split lost or duplicated events"
    )


def test_mlflow_records_the_run_contract(training: dict):
    run_id = training.get("run_id")
    assert run_id, (
        "training produced no MLflow run; a model that is not tracked cannot "
        "be compared, reproduced or promoted"
    )

    payload = _get("/api/2.0/mlflow/runs/get", run_id=run_id)["run"]
    data = payload["data"]
    params = {item["key"]: item["value"] for item in data["params"]}
    metrics = {item["key"]: item["value"] for item in data["metrics"]}

    assert params["split_strategy"] == "time"
    assert params["include_current_event"] == "False", (
        "the run still counts the current event in the features"
    )
    assert params["seed"] == str(training["params"]["seed"])
    for name in ("train_start", "train_end", "test_start", "test_end"):
        assert params.get(name), f"the run does not record {name}"
    for name in ("train_rows", "test_rows"):
        assert params.get(name), f"the run does not record {name}"

    feature_list = [item for item in params["features"].split(",") if item]
    assert len(feature_list) >= 6, (
        f"the run records only {len(feature_list)} features"
    )

    for name in ("accuracy", "precision", "recall", "f1", "roc_auc"):
        assert name in metrics, f"the run does not log {name}"
        assert math.isfinite(metrics[name]), f"{name} is not a finite number"
    for name in ("baseline_precision", "baseline_recall", "baseline_roc_auc"):
        assert name in metrics, (
            f"the run does not log {name}; the model is not compared with the "
            "rule baseline on the same holdout"
        )


def test_the_registered_version_belongs_to_this_run(training: dict):
    run_id = training.get("run_id")
    assert run_id, "there is no run to register"

    payload = _get(
        "/api/2.0/mlflow/model-versions/search",
        filter=f"name='{MODEL_NAME}'",
    )
    versions = payload.get("model_versions", [])
    assert versions, (
        f"no version of {MODEL_NAME!r} is registered; a model that is not "
        "registered cannot be served by version"
    )

    latest = max(versions, key=lambda item: int(item["version"]))
    assert latest["run_id"] == run_id, (
        f"the latest registered version ({latest['version']}) points at run "
        f"{latest['run_id']}, not the run this check trained ({run_id}); the "
        "registry is stale"
    )
    assert latest.get("status") == "READY", (
        f"the registered version is {latest.get('status')!r}, not READY"
    )
    assert latest.get("source"), (
        "the registered version has no model artifact source"
    )


def test_the_model_is_usable_on_the_holdout(training: dict):
    metrics = training["metrics"]
    assert metrics["recall"] >= 0.8, (
        f"recall is {metrics['recall']:.2f}; the model misses most attacks"
    )
    assert metrics["precision"] >= 0.8, (
        f"precision is {metrics['precision']:.2f}; most blocks are false"
    )
    assert metrics["roc_auc"] >= 0.8, (
        f"roc_auc is {metrics['roc_auc']:.2f}; the model barely separates the "
        "classes"
    )
    assert training["baseline"]["roc_auc"] >= 0.0


def _sample_request() -> dict:
    from ml import features

    events = features.load_events()
    last_day = events["event_time"].dt.date.max()
    candidates = events[events["event_time"].dt.date == last_day].sort_values(
        "event_time"
    )
    row = candidates.iloc[len(candidates) // 2]
    return {
        "user_id": row["user_id"],
        "event_time": row["event_time"].isoformat().replace("+00:00", "Z"),
        "source_ip": row["source_ip"],
        "country": row["country"],
        "device_id": row["device_id"],
        "risk_score": str(row["risk_score"]),
    }


def test_shadow_scoring_returns_both_decisions(training: dict):
    request = _sample_request()
    result = subprocess.run(
        [
            sys.executable,
            "ml/score.py",
            "--user-id",
            request["user_id"],
            "--event-time",
            request["event_time"],
            "--source-ip",
            request["source_ip"],
            "--country",
            request["country"],
            "--device-id",
            request["device_id"],
            "--risk-score",
            request["risk_score"],
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=300,
    )
    assert result.returncode == 0, (
        f"ml/score.py failed\n{result.stdout[-4000:]}\n{result.stderr[-4000:]}"
    )
    payload = json.loads(result.stdout.strip().splitlines()[-1])

    assert payload.get("shadow") is True, (
        "shadow mode is off; the model cannot be compared with the rules "
        "without changing the response"
    )
    assert payload.get("model_decision") in {"allow", "block", "mfa"}
    assert payload.get("rule_decision") in {"allow", "block", "mfa"}, (
        "shadow mode did not produce a rule decision for the same request"
    )
    assert 0.0 <= float(payload["model_score"]) <= 1.0


def test_promotion_and_rollback_are_written_down(training: dict):
    text = PROMOTION.read_text(encoding="utf-8")
    lowered = text.lower()
    for heading in ("## shadow", "## promotion", "## rollback"):
        assert heading in lowered, f"the promotion plan is missing {heading!r}"
    assert "TODO(learner)" not in text, "the promotion plan is still a placeholder"

    for term in ("precision", "latency", "owner", "shadow"):
        assert term in lowered, f"the promotion plan does not mention {term!r}"

    numbers = re.findall(r"\b\d+(?:\.\d+)?%?\b", text)
    assert len(numbers) >= 4, (
        "the promotion plan has no measurable thresholds; 'better AUC' is not "
        "a rollout rule"
    )
