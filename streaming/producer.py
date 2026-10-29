"""Fixture producer for the login events topic."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

from confluent_kafka import Producer
from fastavro import parse_schema, schemaless_writer

from . import config
from .schemas import SCHEMA

ROOT = Path("/workspace")
EVENTS_DIR = ROOT / "fixtures" / "events"


def rows():
    for path in sorted(EVENTS_DIR.glob("events-*.jsonl")):
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    yield json.loads(line)


def make_producer() -> Producer:
    return Producer(
        {
            "bootstrap.servers": config.BROKER,
            "client.id": "lab-login-events",
            "acks": config.ACKS,
            "enable.idempotence": config.ENABLE_IDEMPOTENCE,
            "retries": 5,
        }
    )


def produce(limit: int | None = None) -> int:
    schema = parse_schema(SCHEMA)
    producer = make_producer()
    sent = 0
    for row in rows():
        buffer = BytesIO()
        schemaless_writer(buffer, schema, row)
        key = row[config.MESSAGE_KEY] if config.MESSAGE_KEY else None
        producer.produce(
            config.TOPIC,
            key=key.encode("utf-8") if key is not None else None,
            value=buffer.getvalue(),
        )
        producer.poll(0)
        sent += 1
        if limit is not None and sent >= limit:
            break
    producer.flush(60)
    return sent
