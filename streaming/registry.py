"""Small Apicurio Registry v2 client used by the exercises and checks."""

from __future__ import annotations

import json

import requests

from . import config
from .schemas import SCHEMA, schema_text


def _artifact_url(subject: str | None = None) -> str:
    subject = subject or config.SCHEMA_SUBJECT
    return f"{config.REGISTRY_URL}/groups/default/artifacts/{subject}"


def get_schema(subject: str | None = None) -> dict | None:
    response = requests.get(_artifact_url(subject), timeout=10)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def register_schema(subject: str | None = None) -> dict:
    subject = subject or config.SCHEMA_SUBJECT
    existing = get_schema(subject)
    if existing is not None:
        return existing
    response = requests.post(
        f"{config.REGISTRY_URL}/groups/default/artifacts",
        headers={
            "Content-Type": "application/json",
            "X-Registry-ArtifactId": subject,
            "X-Registry-ArtifactType": "AVRO",
        },
        data=schema_text(),
        timeout=10,
    )
    if response.status_code == 409:
        return get_schema(subject) or SCHEMA
    response.raise_for_status()
    return get_schema(subject) or SCHEMA


def set_compatibility(mode: str | None = None, subject: str | None = None) -> None:
    mode = mode or config.SCHEMA_COMPATIBILITY
    subject = subject or config.SCHEMA_SUBJECT
    url = f"{_artifact_url(subject)}/rules/COMPATIBILITY"
    response = requests.put(url, json={"config": mode}, timeout=10)
    if response.status_code == 404:
        response = requests.post(
            f"{_artifact_url(subject)}/rules",
            json={"type": "COMPATIBILITY", "config": mode},
            timeout=10,
        )
    response.raise_for_status()


def get_compatibility(subject: str | None = None) -> str | None:
    subject = subject or config.SCHEMA_SUBJECT
    response = requests.get(
        f"{_artifact_url(subject)}/rules/COMPATIBILITY", timeout=10
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json().get("config")


def update_schema(schema: dict, subject: str | None = None) -> requests.Response:
    subject = subject or config.SCHEMA_SUBJECT
    return requests.put(
        _artifact_url(subject),
        headers={"Content-Type": "application/json"},
        data=json.dumps(schema),
        timeout=10,
    )


def delete_schema(subject: str | None = None) -> None:
    subject = subject or config.SCHEMA_SUBJECT
    response = requests.delete(_artifact_url(subject), timeout=10)
    # Apicurio v2 refuses to delete an artifact that still has versions. The
    # lab keeps the artifact and lets setup update its rule instead.
    if response.status_code not in (204, 404, 405):
        response.raise_for_status()
