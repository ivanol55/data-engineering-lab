"""Login risk decision service (module 7).

The service combines three inputs:

* Postgres: the system of record for identity and account status.
* Valkey: the fast path for threat intel and the last country seen per user.
* Kafka: the append-only decision log.

The rules live in ``rules.py`` and the learner decisions in ``config.py``. The
I/O is here so a dependency failure has one explicit, testable behaviour.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone

import psycopg
import redis
from confluent_kafka import Producer
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

import config
import rules

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("decision-api")

app = FastAPI(
    title="Login risk decision service",
    version="1.0.0",
    description="Module 7 decision service: allow, challenge with MFA, or block.",
)

DECISIONS = Counter(
    "lab_decisions_total",
    "Decisions returned by the service.",
    ["decision", "reason"],
)
LATENCY = Histogram(
    "lab_decision_latency_seconds",
    "End-to-end decision latency.",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)
DEPENDENCY_ERRORS = Counter(
    "lab_dependency_errors_total",
    "Dependency failures observed while deciding.",
    ["dependency"],
)
LOG_FAILURES = Counter(
    "lab_decision_log_failures_total",
    "Decision events that could not be published.",
)
CACHE_HITS = Counter(
    "lab_decision_cache_hits_total",
    "Requests answered from the idempotency cache.",
)

_producer: Producer | None = None


class LoginAttempt(BaseModel):
    user_id: str
    source_ip: str
    country: str | None = None
    device_id: str | None = None
    mfa_used: bool = False
    request_id: str | None = Field(default=None, max_length=128)


class Decision(BaseModel):
    request_id: str
    decision: str
    reason: str
    rule_version: str
    latency_ms: float


class DependencyError(RuntimeError):
    def __init__(self, dependency: str, message: str) -> None:
        super().__init__(message)
        self.dependency = dependency


def _valkey() -> redis.Redis:
    return redis.Redis.from_url(
        config.VALKEY_URL,
        socket_timeout=config.VALKEY_TIMEOUT_SECONDS,
        socket_connect_timeout=config.VALKEY_TIMEOUT_SECONDS,
        decode_responses=True,
    )


def _maybe_fail(dependency: str, header_value: str | None) -> None:
    """Lab-only fault injection used by the module 7 checks."""
    if (
        config.ALLOW_FAULT_INJECTION
        and header_value
        and header_value.strip().lower() == dependency
    ):
        raise DependencyError(dependency, f"injected {dependency} failure")


def load_user(user_id: str, fail_header: str | None) -> dict | None:
    _maybe_fail("postgres", fail_header)
    try:
        with psycopg.connect(
            connect_timeout=config.POSTGRES_TIMEOUT_SECONDS,
            row_factory=dict_row,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT user_id::text AS user_id,
                           account_status,
                           deleted_at,
                           home_country,
                           mfa_enabled
                      FROM users
                     WHERE user_id = %s
                    """,
                    (user_id,),
                )
                return cursor.fetchone()
    except psycopg.Error as exc:
        DEPENDENCY_ERRORS.labels("postgres").inc()
        raise DependencyError("postgres", str(exc)) from exc


def load_intel(source_ip: str, fail_header: str | None) -> str | None:
    _maybe_fail("valkey", fail_header)
    try:
        return _valkey().get(f"intel:{source_ip}")
    except redis.RedisError as exc:
        DEPENDENCY_ERRORS.labels("valkey").inc()
        raise DependencyError("valkey", str(exc)) from exc


def load_last_country(user_id: str, fail_header: str | None) -> str | None:
    _maybe_fail("valkey", fail_header)
    try:
        return _valkey().get(f"last_country:{user_id}")
    except redis.RedisError as exc:
        DEPENDENCY_ERRORS.labels("valkey").inc()
        raise DependencyError("valkey", str(exc)) from exc


def remember_country(user_id: str, country: str | None) -> None:
    if not country:
        return
    try:
        _valkey().setex(
            f"last_country:{user_id}",
            config.LAST_COUNTRY_TTL_SECONDS,
            country,
        )
    except redis.RedisError:
        # A failed write only loses a future travel signal. The current
        # decision is already made and logged; do not fail it now.
        DEPENDENCY_ERRORS.labels("valkey").inc()


def cached_decision(request_id: str) -> dict | None:
    try:
        raw = _valkey().get(f"decision:{request_id}")
    except redis.RedisError:
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def cache_decision(request_id: str, payload: dict) -> None:
    try:
        _valkey().setex(
            f"decision:{request_id}",
            config.DECISION_CACHE_TTL_SECONDS,
            json.dumps(payload),
        )
    except redis.RedisError:
        pass


def _get_producer() -> Producer | None:
    global _producer
    if not config.DECISION_LOG_ENABLED:
        return None
    if _producer is None:
        _producer = Producer(
            {
                "bootstrap.servers": config.KAFKA_BOOTSTRAP,
                "acks": "all",
                "enable.idempotence": True,
                "message.timeout.ms": 2000,
            }
        )
    return _producer


def publish_decision(event: dict) -> None:
    producer = _get_producer()
    if producer is None:
        return
    try:
        producer.produce(
            config.DECISION_TOPIC,
            key=event["user_id"],
            value=json.dumps(event, separators=(",", ":")),
        )
        producer.poll(0)
        producer.flush(1.0)
    except Exception as exc:  # noqa: BLE001 - audit failure must be visible
        LOG_FAILURES.inc()
        log.error("could not publish decision event: %s", exc)


def _finish(
    *,
    request_id: str,
    decision: str,
    reason: str,
    latency_ms: float,
    attempt: LoginAttempt,
) -> dict:
    payload = {
        "request_id": request_id,
        "decision": decision,
        "reason": reason,
        "rule_version": config.RULE_VERSION,
        "latency_ms": round(latency_ms, 3),
    }
    DECISIONS.labels(decision, reason).inc()
    LATENCY.observe(latency_ms / 1000.0)
    publish_decision(
        {
            **payload,
            "decision_id": str(uuid.uuid4()),
            "user_id": attempt.user_id,
            "source_ip": attempt.source_ip,
            "country": attempt.country,
            "device_id": attempt.device_id,
            "mfa_used": attempt.mfa_used,
            "decided_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    cache_decision(request_id, payload)
    return payload


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness only: the process is up. /ready checks dependencies."""
    return {"status": "ok", "module": "07-decision-service"}


@app.get("/ready")
def ready() -> dict[str, str]:
    checks: dict[str, str] = {}
    try:
        redis.Redis.from_url(
            config.VALKEY_URL,
            socket_timeout=config.VALKEY_TIMEOUT_SECONDS,
        ).ping()
        checks["valkey"] = "ok"
    except Exception as exc:  # noqa: BLE001 - surface the reason
        raise HTTPException(status_code=503, detail=f"valkey: {exc}") from exc

    try:
        with psycopg.connect(connect_timeout=config.POSTGRES_TIMEOUT_SECONDS) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        checks["postgres"] = "ok"
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"postgres: {exc}") from exc

    return {"status": "ready", **checks}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/decide", response_model=Decision)
def decide(
    attempt: LoginAttempt,
    request: Request,
    x_lab_fail_dependency: str | None = Header(default=None),
) -> dict:
    started = time.perf_counter()
    request_id = attempt.request_id or str(uuid.uuid4())

    cached = cached_decision(request_id)
    if cached is not None:
        CACHE_HITS.inc()
        return cached

    try:
        user = load_user(attempt.user_id, x_lab_fail_dependency)
        if user is None:
            decision, reason = rules.decide(
                user=None,
                intel_value=None,
                last_country=None,
                country=attempt.country,
            )
        else:
            intel_value = load_intel(attempt.source_ip, x_lab_fail_dependency)
            last_country = load_last_country(attempt.user_id, x_lab_fail_dependency)
            decision, reason = rules.decide(
                user=user,
                intel_value=intel_value,
                last_country=last_country,
                country=attempt.country,
            )
    except DependencyError as exc:
        log.warning("dependency %s failed: %s", exc.dependency, exc)
        decision = config.FAIL_MODE
        reason = "dependency_unavailable"

    latency_ms = (time.perf_counter() - started) * 1000
    payload = _finish(
        request_id=request_id,
        decision=decision,
        reason=reason,
        latency_ms=latency_ms,
        attempt=attempt,
    )

    if decision in {"allow", "mfa"} and reason != "dependency_unavailable":
        remember_country(attempt.user_id, attempt.country)

    return payload
