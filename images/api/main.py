"""Decision service placeholder (module 7).

This process exists so the `serving` profile is real: it starts, it reports
health, and it fails loudly when a dependency is missing. It does **not** make
login decisions yet. Module 7 replaces the 501 with rules backed by Valkey and
the batch tables.

Keeping `/decide` as an explicit 501 is deliberate. A stub that returned
"allow" would look healthy while answering every login incorrectly.
"""

from __future__ import annotations

import os

import psycopg
import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="Login risk decision service",
    version="0.1.0",
    description="Module 7 placeholder. /decide is not implemented yet.",
)

VALKEY_URL = os.getenv("VALKEY_URL", "redis://valkey:6379/0")


class LoginAttempt(BaseModel):
    user_id: str
    source_ip: str
    country: str | None = None
    device_id: str | None = None
    mfa_used: bool = False


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness only: the process is up. /ready checks dependencies."""
    return {"status": "ok", "module": "placeholder"}


@app.get("/ready")
def ready() -> dict[str, str]:
    checks: dict[str, str] = {}
    try:
        redis.Redis.from_url(VALKEY_URL, socket_timeout=2).ping()
        checks["valkey"] = "ok"
    except Exception as exc:  # noqa: BLE001 - surface the reason
        raise HTTPException(status_code=503, detail=f"valkey: {exc}") from exc

    try:
        with psycopg.connect(connect_timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        checks["postgres"] = "ok"
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"postgres: {exc}") from exc

    return {"status": "ready", **checks}


@app.post("/decide")
def decide(attempt: LoginAttempt) -> dict[str, object]:
    raise HTTPException(
        status_code=501,
        detail=(
            "Module 7 is not implemented. Build the decision rules, the Valkey "
            "lookups, and the decision event producer before calling this."
        ),
    )
