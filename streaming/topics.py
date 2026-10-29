"""Topic administration for module 4."""

from __future__ import annotations

from confluent_kafka.admin import AdminClient, NewTopic
from confluent_kafka import KafkaException

from . import config


def admin() -> AdminClient:
    return AdminClient({"bootstrap.servers": config.BROKER})


def create_topic() -> None:
    topic = NewTopic(
        config.TOPIC,
        num_partitions=config.PARTITION_COUNT,
        replication_factor=1,
        config={
            "cleanup.policy": "delete",
            # Seven days matches the fixture window: a backfill that needs
            # older events must come from the lakehouse, not the log.
            "retention.ms": str(7 * 24 * 60 * 60 * 1000),
        },
    )
    client = admin()
    futures = client.create_topics([topic])
    for future in futures.values():
        try:
            future.result(timeout=30)
        except KafkaException as exc:
            if "already exists" not in str(exc).lower():
                raise


def delete_topic() -> None:
    client = admin()
    futures = client.delete_topics([config.TOPIC])
    for future in futures.values():
        try:
            future.result(timeout=30)
        except KafkaException:
            pass


def describe_topic() -> dict:
    metadata = admin().list_topics(timeout=10)
    topic = metadata.topics.get(config.TOPIC)
    if topic is None:
        return {}
    return {
        "partitions": len(topic.partitions),
        "error": topic.error,
    }
