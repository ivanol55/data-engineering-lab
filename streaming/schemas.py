"""Avro schema shared by the producer, the consumer and the registry."""

from __future__ import annotations

import json

SCHEMA = {
    "type": "record",
    "name": "LoginEvent",
    "namespace": "com.example.lab",
    "fields": [
        {"name": "event_id", "type": "string"},
        {"name": "event_time", "type": "string"},
        {"name": "user_id", "type": "string"},
        {"name": "email", "type": ["null", "string"], "default": None},
        {"name": "session_id", "type": ["null", "string"], "default": None},
        {"name": "source_ip", "type": ["null", "string"], "default": None},
        {"name": "country", "type": ["null", "string"], "default": None},
        {"name": "city", "type": ["null", "string"], "default": None},
        {"name": "latitude", "type": ["null", "double"], "default": None},
        {"name": "longitude", "type": ["null", "double"], "default": None},
        {"name": "device_id", "type": ["null", "string"], "default": None},
        {"name": "device_type", "type": ["null", "string"], "default": None},
        {"name": "operating_system", "type": ["null", "string"], "default": None},
        {"name": "browser", "type": ["null", "string"], "default": None},
        {"name": "auth_method", "type": ["null", "string"], "default": None},
        {"name": "mfa_used", "type": ["null", "boolean"], "default": None},
        {"name": "outcome", "type": ["null", "string"], "default": None},
        {"name": "failure_reason", "type": ["null", "string"], "default": None},
        {"name": "risk_score", "type": ["null", "long"], "default": None},
        {"name": "is_attack", "type": ["null", "boolean"], "default": None},
        {"name": "attack_type", "type": ["null", "string"], "default": None},
        {"name": "attack_id", "type": ["null", "string"], "default": None},
        {"name": "generator_version", "type": ["null", "string"], "default": None},
    ],
}


def schema_text() -> str:
    return json.dumps(SCHEMA, indent=2)
