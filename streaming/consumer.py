"""At-least-once consumer with a replay-safe file sink."""

from __future__ import annotations

import json
import uuid
from io import BytesIO
from pathlib import Path

from confluent_kafka import Consumer
from fastavro import parse_schema, schemaless_reader

from . import config
from .schemas import SCHEMA


def _existing_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                ids.add(json.loads(line)["event_id"])
            except (json.JSONDecodeError, KeyError):
                continue
    return ids


def consume(limit: int | None = None, replay: bool = False) -> dict[str, int]:
    group = config.CONSUMER_GROUP
    if replay:
        # A new group starts at the earliest offset. The sink, not the
        # consumer group, is responsible for idempotence.
        group = f"{group}-replay-{uuid.uuid4()}"

    settings = {
        "bootstrap.servers": config.BROKER,
        "group.id": group,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": config.AUTO_COMMIT,
    }
    if not config.AUTO_COMMIT:
        settings["enable.auto.offset.store"] = False

    consumer = Consumer(settings)
    consumer.subscribe([config.TOPIC])
    schema = parse_schema(SCHEMA)
    sink = Path(config.SINK_PATH)
    sink.parent.mkdir(parents=True, exist_ok=True)
    seen = _existing_ids(sink) if config.SINK_IDEMPOTENT else set()

    processed = 0
    duplicates = 0
    idle_polls = 0
    try:
        while True:
            message = consumer.poll(1.0)
            if message is None:
                idle_polls += 1
                if idle_polls >= 3:
                    break
                continue
            if message.error():
                raise RuntimeError(message.error())
            idle_polls = 0
            row = schemaless_reader(BytesIO(message.value()), schema)
            event_id = row["event_id"]

            if config.SINK_IDEMPOTENT and event_id in seen:
                duplicates += 1
            else:
                with sink.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row, sort_keys=True) + "\n")
                seen.add(event_id)
                processed += 1

            if not config.AUTO_COMMIT:
                # Commit only after the sink write has returned.
                consumer.commit(message=message, asynchronous=False)

            if limit is not None and processed >= limit:
                break
    finally:
        consumer.close()

    return {"processed": processed, "duplicates": duplicates}
