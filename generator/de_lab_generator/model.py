"""Event and threat-intel schemas, constants and deterministic identifiers."""

from __future__ import annotations

import uuid

GENERATOR_VERSION = "1.0.0"
EVENT_NAMESPACE = uuid.UUID("6f6d0e2a-3f39-5b4a-9b3e-2f6d1c7a8b90")
SESSION_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-5a7b-8c9d-0e1f2a3b4c5d")
DEVICE_NAMESPACE = uuid.UUID("f0e1d2c3-b4a5-5968-7788-99aabbccddee")

OUTCOMES = ("allow", "mfa_challenge", "block")
ATTACK_TYPES = (
    "credential_stuffing",
    "brute_force",
    "impossible_travel",
    "mfa_fatigue",
    "account_takeover",
    "new_device",
)
DEVICE_TYPES = ("desktop", "mobile", "tablet")
OPERATING_SYSTEMS = {
    "desktop": ("macOS 15", "Windows 11", "Ubuntu 24.04"),
    "mobile": ("iOS 18", "Android 15"),
    "tablet": ("iPadOS 18", "Android 15"),
}
BROWSERS = ("Chrome", "Firefox", "Safari", "Edge")
AUTH_METHODS = ("password", "sso", "api_key")

# Only documentation / private address ranges are used. Nothing here can
# resolve to a real host, which keeps generated logs safe to publish.
NORMAL_NET = "192.0.2"
TRAVEL_NET = "198.51.100"
ATTACK_NET = "203.0.113"

EVENT_COLUMNS = {
    "event_id": {"data_type": "text", "nullable": False},
    "event_time": {"data_type": "timestamp", "timezone": True, "nullable": False},
    "user_id": {"data_type": "text", "nullable": False},
    "email": {"data_type": "text"},
    "session_id": {"data_type": "text"},
    "source_ip": {"data_type": "text"},
    "country": {"data_type": "text"},
    "city": {"data_type": "text"},
    "latitude": {"data_type": "double"},
    "longitude": {"data_type": "double"},
    "device_id": {"data_type": "text"},
    "device_type": {"data_type": "text"},
    "operating_system": {"data_type": "text"},
    "browser": {"data_type": "text"},
    "auth_method": {"data_type": "text"},
    "mfa_used": {"data_type": "bool"},
    "outcome": {"data_type": "text"},
    "failure_reason": {"data_type": "text"},
    "risk_score": {"data_type": "bigint"},
    "is_attack": {"data_type": "bool"},
    "attack_type": {"data_type": "text"},
    "attack_id": {"data_type": "text"},
    "generator_version": {"data_type": "text"},
}

THREAT_INTEL_COLUMNS = {
    "indicator": {"data_type": "text", "nullable": False},
    "indicator_type": {"data_type": "text"},
    "threat_type": {"data_type": "text"},
    "confidence": {"data_type": "bigint"},
    "severity": {"data_type": "text"},
    "source": {"data_type": "text"},
    "description": {"data_type": "text"},
    "valid_from": {"data_type": "date", "nullable": False},
    "valid_to": {"data_type": "date"},
    "updated_at": {"data_type": "timestamp", "timezone": True},
    "generator_version": {"data_type": "text"},
}


def event_id(seed: int, day: str, sequence: int) -> str:
    return str(uuid.uuid5(EVENT_NAMESPACE, f"{seed}:{day}:{sequence}"))


def session_id(seed: int, user_id: str, day: str) -> str:
    return str(uuid.uuid5(SESSION_NAMESPACE, f"{seed}:{user_id}:{day}"))


def device_id(user_id: str, slot: int = 0) -> str:
    return str(uuid.uuid5(DEVICE_NAMESPACE, f"{user_id}:{slot}"))
