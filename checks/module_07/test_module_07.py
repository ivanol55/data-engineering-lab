"""Behavioural checks for module 7.

The checks talk to the deployed decision service over HTTP. They do not import
``images/api``: the contract is the running container, with the config baked
into its image.
"""

from __future__ import annotations

import json
import statistics
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pytest
import redis
import requests
from confluent_kafka import Consumer
from confluent_kafka.admin import AdminClient, NewTopic

ROOT = Path("/workspace")
API = "http://api:8000"
VALKEY_URL = "redis://valkey:6379/0"
BROKER = "kafka:9092"
DECISION_TOPIC = "login.decisions"


def _valkey() -> redis.Redis:
    return redis.Redis.from_url(VALKEY_URL, decode_responses=True)


def _connect():
    return psycopg.connect(host="postgres", dbname="app", user="app", password="app")


def _active_users(limit: int = 12) -> list[dict]:
    with _connect() as connection:
        with connection.cursor(row_factory=psycopg.rows.dict_row) as cursor:
            cursor.execute(
                """
                select user_id::text as user_id, home_country
                  from users
                 where account_status = 'active'
                   and deleted_at is null
                 order by user_id
                 limit %s
                """,
                (limit,),
            )
            return list(cursor.fetchall())


def _set_user(user_id: str, **columns) -> None:
    assignments = ", ".join(f"{name} = %s" for name in columns)
    values = list(columns.values())
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"update users set {assignments} where user_id = %s",
                [*values, user_id],
            )


def _ensure_topic(name: str) -> None:
    admin = AdminClient({"bootstrap.servers": BROKER})
    futures = admin.create_topics(
        [NewTopic(name, num_partitions=3, replication_factor=1)]
    )
    for future in futures.values():
        try:
            future.result(timeout=30)
        except Exception as exc:  # noqa: BLE001 - already exists is fine
            if "already exists" not in str(exc).lower():
                raise


def _wait_ready(timeout: int = 90) -> None:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            response = requests.get(f"{API}/ready", timeout=2)
            if response.status_code == 200:
                return
            last = f"{response.status_code} {response.text}"
        except requests.RequestException as exc:
            last = str(exc)
        time.sleep(2)
    raise AssertionError(f"the decision service never became ready: {last}")


@pytest.fixture(scope="module", autouse=True)
def clean_state():
    _wait_ready()
    _valkey().flushdb()
    _ensure_topic(DECISION_TOPIC)
    yield


def _post(
    payload: dict,
    *,
    fail_dependency: str | None = None,
    timeout: float = 5.0,
) -> dict:
    headers = {"content-type": "application/json"}
    if fail_dependency:
        headers["x-lab-fail-dependency"] = fail_dependency
    response = requests.post(
        f"{API}/decide", json=payload, headers=headers, timeout=timeout
    )
    assert response.status_code == 200, (
        f"/decide returned {response.status_code}: {response.text}"
    )
    return response.json()


def _attempt(user: dict, *, country: str | None = None, ip: str = "192.0.2.10") -> dict:
    return {
        "user_id": user["user_id"],
        "source_ip": ip,
        "country": country if country is not None else user["home_country"],
        "device_id": "check-device",
        "mfa_used": False,
        "request_id": str(uuid.uuid4()),
    }


def test_known_user_is_allowed():
    user = _active_users(1)[0]
    _valkey().delete(f"last_country:{user['user_id']}")
    body = _post(_attempt(user, ip="192.0.2.11"))
    assert body["decision"] == "allow", body
    assert body["reason"] == "default", body
    assert body["rule_version"], "every decision needs a rule version"
    assert body["latency_ms"] >= 0


def test_unknown_user_is_not_allowed():
    user = {"user_id": str(uuid.uuid4()), "home_country": "Germany"}
    body = _post(_attempt(user, ip="192.0.2.12"))
    assert body["decision"] == "block", (
        "an unknown user was allowed; missing identity data is not low risk"
    )
    assert body["reason"] == "unknown_user", body


def test_deleted_user_is_blocked():
    user = _active_users(12)[1]
    _valkey().delete(f"last_country:{user['user_id']}")
    try:
        _set_user(
            user["user_id"],
            deleted_at=datetime.now(timezone.utc),
        )
        body = _post(_attempt(user, ip="192.0.2.13"))
    finally:
        _set_user(user["user_id"], deleted_at=None)
    assert body["decision"] == "block", (
        "a deleted account was allowed; enable the account-status check"
    )
    assert body["reason"] == "deleted_user", body


def test_inactive_user_is_blocked():
    user = _active_users(12)[2]
    _valkey().delete(f"last_country:{user['user_id']}")
    try:
        _set_user(user["user_id"], account_status="suspended")
        body = _post(_attempt(user, ip="192.0.2.14"))
    finally:
        _set_user(user["user_id"], account_status="active")
    assert body["decision"] == "block", (
        "a suspended account was allowed; enable the account-status check"
    )
    assert body["reason"] == "inactive_account", body


def test_fresh_intel_blocks_the_source_ip():
    user = _active_users(12)[3]
    ip = "198.51.100.20"
    _valkey().delete(f"last_country:{user['user_id']}")
    _valkey().set(f"intel:{ip}", str(time.time()))
    body = _post(_attempt(user, ip=ip))
    assert body["decision"] == "block", (
        "a source IP on the current intel list was allowed; enable the intel "
        "lookup"
    )
    assert body["reason"] == "threat_intel", body


def test_expired_intel_does_not_block():
    user = _active_users(12)[4]
    ip = "198.51.100.21"
    _valkey().delete(f"last_country:{user['user_id']}")
    _valkey().set(f"intel:{ip}", str(time.time() - 7200))
    body = _post(_attempt(user, ip=ip))
    assert body["decision"] != "block", (
        "a two-hour-old indicator still blocked; the intel TTL is longer than "
        "the feed cadence"
    )
    assert body["reason"] == "default", body


def test_impossible_travel_challenges_with_mfa():
    user = _active_users(12)[5]
    _valkey().set(f"last_country:{user['user_id']}", "France")
    body = _post(_attempt(user, country="Germany", ip="192.0.2.15"))
    assert body["decision"] == "mfa", (
        "a country change between requests was allowed without a challenge"
    )
    assert body["reason"] == "impossible_travel", body


@pytest.mark.parametrize("dependency", ["postgres", "valkey"])
def test_dependency_failure_fails_closed(dependency: str):
    user = _active_users(12)[6]
    body = _post(
        _attempt(user, ip="192.0.2.16"),
        fail_dependency=dependency,
    )
    assert body["decision"] == "block", (
        f"a {dependency} failure returned {body['decision']!r}; a security "
        "decision must fail closed"
    )
    assert body["reason"] == "dependency_unavailable", body


def test_decision_is_logged_to_kafka_with_the_same_request_id():
    user = _active_users(12)[7]
    request_id = str(uuid.uuid4())
    payload = _attempt(user, ip="192.0.2.17")
    payload["request_id"] = request_id
    body = _post(payload)
    assert body["request_id"] == request_id

    consumer = Consumer(
        {
            "bootstrap.servers": BROKER,
            "group.id": f"decision-log-check-{uuid.uuid4()}",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([DECISION_TOPIC])
    found = None
    deadline = time.time() + 25
    try:
        while time.time() < deadline and found is None:
            message = consumer.poll(1.0)
            if message is None or message.error():
                continue
            event = json.loads(message.value())
            if event.get("request_id") == request_id:
                found = event
    finally:
        consumer.close()

    assert found is not None, (
        "no decision event with the response request_id reached Kafka; a "
        "decision without a log is not auditable"
    )
    assert found["decision"] == body["decision"]
    assert found["user_id"] == user["user_id"]
    assert found["rule_version"] == body["rule_version"]
    assert found.get("decided_at"), "the log event needs a decision timestamp"


def test_a_retried_request_id_returns_the_same_decision():
    user = _active_users(12)[8]
    payload = _attempt(user, ip="192.0.2.18")
    first = _post(payload)
    second = _post(payload)
    assert first["decision"] == second["decision"]
    assert first["reason"] == second["reason"]
    assert first["request_id"] == second["request_id"]


def test_metrics_expose_decisions_and_latency():
    response = requests.get(f"{API}/metrics", timeout=5)
    assert response.status_code == 200
    text = response.text
    assert "lab_decisions_total" in text, "no decision counter is exported"
    assert "lab_decision_latency_seconds" in text, "no latency histogram is exported"


def test_p95_latency_stays_below_the_caller_budget():
    user = _active_users(12)[9]
    _valkey().delete(f"last_country:{user['user_id']}")
    samples = []
    for _ in range(20):
        payload = _attempt(user, ip="192.0.2.19")
        started = time.perf_counter()
        _post(payload, timeout=2.0)
        samples.append(time.perf_counter() - started)
    p95 = statistics.quantiles(samples, n=20)[-1]
    assert p95 < 1.0, (
        f"p95 latency was {p95 * 1000:.0f} ms; the dependency budget must "
        "stay below the caller timeout"
    )
