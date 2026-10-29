"""Debezium PostgreSQL connector lifecycle."""

from __future__ import annotations

import time

import requests

from . import config


def connector_config() -> dict[str, str]:
    return {
        "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
        "tasks.max": "1",
        "plugin.name": "pgoutput",
        "slot.name": config.SLOT_NAME,
        "publication.name": config.PUBLICATION_NAME,
        "publication.autocreate.mode": "filtered",
        "database.hostname": "postgres",
        "database.port": "5432",
        "database.user": "app",
        "database.password": "app",
        "database.dbname": "app",
        "topic.prefix": config.TOPIC_PREFIX,
        "table.include.list": config.INCLUDE_TABLES,
        "snapshot.mode": config.SNAPSHOT_MODE,
        "tombstones.on.delete": str(config.EMIT_TOMBSTONES).lower(),
        "schema.history.internal.kafka.bootstrap.servers": "kafka:9092",
        "schema.history.internal.kafka.topic": config.SCHEMA_HISTORY_TOPIC,
        "key.converter": "org.apache.kafka.connect.json.JsonConverter",
        "value.converter": "org.apache.kafka.connect.json.JsonConverter",
        "key.converter.schemas.enable": "false",
        "value.converter.schemas.enable": "false",
        "decimal.handling.mode": "double",
        "time.precision.mode": "connect",
    }


def register() -> dict:
    response = requests.post(
        f"{config.CONNECT_URL}/connectors",
        json={"name": config.CONNECTOR_NAME, "config": connector_config()},
        timeout=30,
    )
    if response.status_code == 409:
        response = requests.put(
            f"{config.CONNECT_URL}/connectors/{config.CONNECTOR_NAME}/config",
            json=connector_config(),
            timeout=30,
        )
    response.raise_for_status()
    return response.json()


def delete() -> None:
    base = f"{config.CONNECT_URL}/connectors/{config.CONNECTOR_NAME}"
    # Deleting the connector does not delete its source offsets. Without this
    # stop + offset reset, a recreated connector resumes at an LSN that the
    # new replication slot no longer has.
    requests.put(f"{base}/stop", timeout=30)
    requests.delete(f"{base}/offsets", timeout=30)
    response = requests.delete(base, timeout=30)
    if response.status_code not in (204, 404):
        response.raise_for_status()


def status() -> dict:
    response = requests.get(
        f"{config.CONNECT_URL}/connectors/{config.CONNECTOR_NAME}/status", timeout=10
    )
    if response.status_code == 404:
        return {}
    response.raise_for_status()
    return response.json()


def wait_running(timeout: int = 120) -> dict:
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        last = status()
        connector = last.get("connector", {}).get("state")
        tasks = last.get("tasks", [])
        if connector == "RUNNING" and tasks and all(
            task.get("state") == "RUNNING" for task in tasks
        ):
            return last
        time.sleep(2)
    raise RuntimeError(f"connector did not reach RUNNING: {last}")
