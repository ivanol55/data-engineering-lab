"""Behavioural checks for module 4."""

from __future__ import annotations

import copy
import json
import sys
import uuid
from io import BytesIO
from pathlib import Path

import pytest
from confluent_kafka import Consumer, TopicPartition
from fastavro import parse_schema, schemaless_reader

import checks.support as support
from streaming import config
from streaming.registry import (
    get_compatibility,
    get_schema,
    set_compatibility,
    update_schema,
)
from streaming.schemas import SCHEMA
from streaming.topics import describe_topic

ROOT = Path("/workspace")
RUN_STREAM = ROOT / "streaming" / "run.py"
SINK = Path(config.SINK_PATH)


@pytest.fixture(scope="module", autouse=True)
def produced_topic():
    support.run([sys.executable, str(RUN_STREAM), "reset"])
    support.run([sys.executable, str(RUN_STREAM), "setup"])
    support.run([sys.executable, str(RUN_STREAM), "produce"])
    yield


def _consume_all() -> list:
    consumer = Consumer(
        {
            "bootstrap.servers": config.BROKER,
            "group.id": f"check-{uuid.uuid4()}",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([config.TOPIC])
    messages = []
    idle = 0
    try:
        while True:
            message = consumer.poll(1.0)
            if message is None:
                idle += 1
                if idle >= 3:
                    break
                continue
            idle = 0
            if message.error():
                raise RuntimeError(message.error())
            messages.append(message)
    finally:
        consumer.close()
    return messages


def _rows(messages: list) -> list[dict]:
    schema = parse_schema(SCHEMA)
    return [
        schemaless_reader(BytesIO(message.value()), schema) for message in messages
    ]


def test_topic_has_the_chosen_partition_count():
    topic = describe_topic()
    assert topic, f"topic {config.TOPIC} does not exist"
    assert topic["partitions"] == 3, (
        f"topic has {topic['partitions']} partitions; three gives room for "
        "three consumers without changing per-user ordering"
    )


def test_schema_is_registered_with_backward_compatibility():
    schema = get_schema()
    assert schema is not None, "no schema is registered for the topic"
    assert schema["name"] == SCHEMA["name"]
    assert get_compatibility() == "BACKWARD", (
        "the registry must reject a field rename, which requires BACKWARD "
        "compatibility"
    )


def test_producer_settings_are_durable():
    assert config.ACKS == "all", "acks=1 acknowledges only the leader"
    assert config.ENABLE_IDEMPOTENCE is True, (
        "an idempotent producer avoids duplicates after a retry"
    )


def test_every_fixture_event_is_in_the_topic_exactly_once():
    messages = _consume_all()
    rows = _rows(messages)
    event_ids = [row["event_id"] for row in rows]
    assert len(rows) == 14_000, f"expected 14,000 events, found {len(rows)}"
    assert len(set(event_ids)) == 14_000, "the topic contains duplicate event ids"


def test_user_events_share_one_partition():
    messages = _consume_all()
    rows = _rows(messages)
    partitions: dict[str, set[int]] = {}
    for message, row in zip(messages, rows):
        partitions.setdefault(row["user_id"], set()).add(message.partition())
    split = {user: parts for user, parts in partitions.items() if len(parts) > 1}
    assert not split, (
        f"{len(split)} users have events on more than one partition; a null "
        "key round-robins a user's events and breaks per-user state"
    )


def test_replay_does_not_duplicate_the_sink():
    SINK.unlink(missing_ok=True)
    for _ in range(2):
        support.run(
            [sys.executable, str(RUN_STREAM), "consume", "--replay"]
        )
    lines = [line for line in SINK.read_text(encoding="utf-8").splitlines() if line]
    ids = {json.loads(line)["event_id"] for line in lines}
    assert len(lines) == 14_000, (
        f"two replays wrote {len(lines)} sink rows for 14,000 events; the sink "
        "is not idempotent"
    )
    assert len(ids) == 14_000


def test_consumer_commits_only_after_processing():
    assert config.AUTO_COMMIT is False, (
        "auto-commit can commit offsets before the sink write"
    )
    SINK.unlink(missing_ok=True)
    support.run(
        [sys.executable, str(RUN_STREAM), "consume", "--limit", "1000"]
    )
    consumer = Consumer(
        {
            "bootstrap.servers": config.BROKER,
            "group.id": config.CONSUMER_GROUP,
        }
    )
    try:
        metadata = consumer.list_topics(config.TOPIC, timeout=10)
        partitions = metadata.topics[config.TOPIC].partitions
        committed = consumer.committed(
            [TopicPartition(config.TOPIC, partition) for partition in partitions]
        )
    finally:
        consumer.close()
    total = sum(max(tp.offset, 0) for tp in committed)
    assert total >= 1000, (
        f"the consumer group committed {total} offsets after processing 1,000 "
        "events; commit after the sink write"
    )


def test_registry_rejects_a_rename_and_accepts_an_optional_field():
    original = get_schema()
    assert original is not None

    # Renaming a required field is the classic incompatible change: old data
    # has `event_id`, the new reader requires `id`, and there is no default.
    incompatible = copy.deepcopy(original)
    for field in incompatible["fields"]:
        if field["name"] == "event_id":
            field["name"] = "id"
            break

    try:
        response = update_schema(incompatible)
        assert response.status_code in (400, 409), (
            "the registry accepted a required-field rename; compatibility is "
            "not BACKWARD"
        )

        compatible = copy.deepcopy(original)
        compatible["fields"].append(
            {"name": "schema_version", "type": ["null", "long"], "default": None}
        )
        response = update_schema(compatible)
        assert response.status_code in (200, 201), (
            f"the registry rejected a new optional field: {response.text}"
        )
    finally:
        # Removing the extra field is compatible under BACKWARD, but the
        # required-field rename above is not. Switch to NONE only while
        # restoring the lab's canonical schema.
        set_compatibility("NONE")
        restore = update_schema(original)
        assert restore.status_code in (200, 201), (
            f"could not restore the original schema: {restore.text}"
        )
        set_compatibility(config.SCHEMA_COMPATIBILITY)
