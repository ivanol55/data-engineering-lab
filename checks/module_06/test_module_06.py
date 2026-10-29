"""Behavioural checks for module 6."""

from __future__ import annotations

import json
import subprocess
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pytest
import requests
from confluent_kafka import Consumer

from flink_jobs import config

ROOT = Path("/workspace")
SETUP = ROOT / "flink_jobs" / "setup.py"
JOB = ROOT / "flink_jobs" / "risk_job.py"
FLINK_REST = "http://flink-jobmanager:8081"


def _run(command: list[str]) -> None:
    result = subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True, timeout=900
    )
    if result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"--- stdout ---\n{result.stdout[-4000:]}\n"
            f"--- stderr ---\n{result.stderr[-4000:]}"
        )


def _cancel_running_jobs() -> None:
    response = requests.get(f"{FLINK_REST}/jobs", timeout=10)
    if response.status_code != 200:
        return
    terminal = {"CANCELED", "FAILED", "FINISHED"}
    for job in response.json().get("jobs", []):
        if job.get("status") not in terminal:
            requests.patch(
                f"{FLINK_REST}/jobs/{job['id']}",
                params={"mode": "cancel"},
                timeout=30,
            )
    # Wait for the cluster to release the Kafka source partitions before the
    # check deletes and recreates the topics.
    deadline = time.time() + 60
    while time.time() < deadline:
        response = requests.get(f"{FLINK_REST}/jobs", timeout=10)
        active = [
            job
            for job in response.json().get("jobs", [])
            if job.get("status") not in terminal
        ]
        if not active:
            return
        time.sleep(2)


def _submit() -> None:
    # The PyFlink client occasionally keeps its gateway process alive after
    # the job has been submitted. Bound it and confirm through the REST API.
    log = Path("/tmp/flink-submit.log")
    subprocess.run(
        [
            "bash",
            "-lc",
            "timeout 60 flink run -m flink-jobmanager:8081 -d "
            f"-py {JOB} > {log} 2>&1",
        ],
        cwd=ROOT,
        timeout=90,
    )
    if not _running_job_or_none():
        raise AssertionError(
            f"flink submit did not create a running job:\n"
            f"{log.read_text(encoding='utf-8')[-4000:]}"
        )


def _running_job_or_none() -> dict | None:
    response = requests.get(f"{FLINK_REST}/jobs/overview", timeout=10)
    if response.status_code != 200:
        return None
    running = [
        job
        for job in response.json().get("jobs", [])
        if job["name"] == config.JOB_NAME and job["state"] == "RUNNING"
    ]
    return max(running, key=lambda job: job["start-time"]) if running else None


def _running_job() -> dict:
    deadline = time.time() + 120
    while time.time() < deadline:
        job = _running_job_or_none()
        if job is not None:
            return job
        time.sleep(2)
    raise AssertionError("the Flink job did not reach RUNNING")


def _output() -> dict[str, dict]:
    consumer = Consumer(
        {
            "bootstrap.servers": config.BOOTSTRAP,
            "group.id": f"flink-check-{uuid.uuid4()}",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([config.OUTPUT_TOPIC])
    latest: dict[str, dict] = {}
    idle = 0
    deadline = time.time() + 90
    try:
        while True:
            message = consumer.poll(1.0)
            if message is None:
                idle += 1
                if not latest and time.time() < deadline:
                    continue
                if idle >= 4:
                    break
                continue
            if message.error():
                continue
            idle = 0
            row = json.loads(message.value())
            latest[row["window_start"]] = row
    finally:
        consumer.close()
    return latest


def _expected_windows() -> dict[datetime, tuple[int, int, int, int]]:
    aggregate: dict[datetime, list] = defaultdict(lambda: [0, 0, set(), 0])
    for path in sorted((ROOT / "fixtures" / "events").glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                event_time = datetime.fromisoformat(
                    row["event_time"].replace("Z", "+00:00")
                ).replace(tzinfo=None)
                start = event_time.replace(
                    minute=(event_time.minute // config.WINDOW_MINUTES)
                    * config.WINDOW_MINUTES,
                    second=0,
                    microsecond=0,
                )
                values = aggregate[start]
                values[0] += 1
                values[1] += int(row["outcome"] != "allow")
                values[2].add(row["user_id"])
                values[3] = max(values[3], row["risk_score"])
    return {
        key: (value[0], value[1], len(value[2]), value[3])
        for key, value in aggregate.items()
    }


@pytest.fixture(scope="module", autouse=True)
def running_job():
    _cancel_running_jobs()
    _run([sys.executable, str(SETUP), "reset"])
    _run([sys.executable, str(SETUP), "setup"])
    _submit()
    _running_job()
    # Give the source time to consume the fixture topic and fire windows.
    time.sleep(25)
    yield


def test_windows_are_computed_from_event_time():
    rows = _output()
    assert rows, "the job produced no windows"
    starts = [datetime.fromisoformat(value) for value in rows]
    assert min(starts) >= datetime(2026, 9, 1), (
        "the output windows are not derived from the 2026-09 fixture timestamps"
    )
    assert max(starts) <= datetime(2026, 9, 8), (
        "processing-time windows leaked into the output"
    )


def test_window_matches_the_batch_aggregation():
    expected = _expected_windows()
    rows = _output()
    start = datetime(2026, 9, 1, 0, 0)
    key = start.isoformat(timespec="seconds")
    assert key in rows, f"window {key} is missing from the job output"
    actual = rows[key]
    want = expected[start]
    assert (
        actual["event_count"],
        actual["failure_count"],
        actual["distinct_users"],
        actual["max_risk"],
    ) == want, (
        f"window {key} is {actual}, batch aggregation is {want}"
    )


def test_checkpoints_complete():
    assert config.CHECKPOINTING is True, (
        "checkpointing is disabled; a TaskManager restart loses all state"
    )
    job = _running_job()
    deadline = time.time() + 60
    counts = {}
    while time.time() < deadline:
        response = requests.get(
            f"{FLINK_REST}/jobs/{job['jid']}/checkpoints", timeout=10
        )
        if response.status_code == 200:
            counts = response.json().get("counts", {})
            if counts.get("completed", 0) >= 1:
                break
        time.sleep(3)
    assert counts.get("completed", 0) >= 1, (
        f"no completed checkpoint: {counts}"
    )


def test_state_ttl_and_lateness_are_configured():
    assert config.STATE_TTL_HOURS > 0, (
        "keyed state has no TTL and grows forever"
    )
    assert config.ALLOWED_LATENESS_SECONDS > 0, (
        "allowed lateness is zero; the generator's late events are dropped"
    )
