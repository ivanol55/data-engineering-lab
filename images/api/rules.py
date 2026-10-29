"""Pure decision rules, kept separate from I/O so they can be tested."""

from __future__ import annotations

import time

import config


def intel_is_fresh(value: str | None, now: float | None = None) -> bool:
    """Intel values are stored as the epoch second when they were seen."""
    if not value:
        return False
    try:
        seen = float(value)
    except (TypeError, ValueError):
        return False
    now = time.time() if now is None else now
    return now - seen <= config.INTEL_TTL_SECONDS


def decide(
    *,
    user: dict | None,
    intel_value: str | None,
    last_country: str | None,
    country: str | None,
) -> tuple[str, str]:
    """Return (decision, reason). The first matching rule wins."""
    if user is None:
        return config.MISSING_USER_DECISION, "unknown_user"

    if config.CHECK_ACCOUNT_STATUS:
        if user.get("deleted_at") is not None:
            return "block", "deleted_user"
        if user.get("account_status") != "active":
            return "block", "inactive_account"

    if config.CHECK_INTEL and intel_is_fresh(intel_value):
        return "block", "threat_intel"

    if last_country and country and last_country != country:
        return "mfa", "impossible_travel"

    return "allow", "default"
