"""Apply Debezium change events to the lab sink tables."""

from __future__ import annotations

import json
import uuid

import psycopg
from confluent_kafka import Consumer

from . import config

USER_TOPIC = f"{config.TOPIC_PREFIX}.public.users"
ROLE_TOPIC = f"{config.TOPIC_PREFIX}.public.roles"

USER_COLUMNS = (
    "user_id",
    "email",
    "full_name",
    "role_id",
    "account_status",
    "department",
    "home_country",
    "home_city",
    "mfa_enabled",
    "created_at",
    "updated_at",
    "deleted_at",
)


def _connect():
    return psycopg.connect(
        host="postgres", dbname="app", user="app", password="app"
    )


def _upsert_user(cursor, row: dict) -> None:
    values = [row.get(column) for column in USER_COLUMNS]
    placeholders = ", ".join(["%s"] * len(USER_COLUMNS))
    columns = ", ".join(USER_COLUMNS)
    if config.SINK_UPSERT:
        updates = ", ".join(
            f"{column} = excluded.{column}"
            for column in USER_COLUMNS
            if column != "user_id"
        )
        cursor.execute(
            f"insert into cdc_users ({columns}) values ({placeholders}) "
            f"on conflict (user_id) do update set {updates}",
            values,
        )
    else:
        # Wrong on purpose: the first snapshot succeeds, later updates and
        # replays are silently ignored.
        cursor.execute(
            f"insert into cdc_users ({columns}) values ({placeholders}) "
            "on conflict (user_id) do nothing",
            values,
        )


def _upsert_role(cursor, row: dict) -> None:
    cursor.execute(
        "insert into cdc_roles (role_id, name, description) "
        "values (%s, %s, %s) on conflict (role_id) do update "
        "set name = excluded.name, description = excluded.description",
        (row.get("role_id"), row.get("name"), row.get("description")),
    )


def apply_event(topic: str, value: dict | None) -> str:
    """Return what the event did: insert/update/delete/tombstone/ignored."""
    if value is None:
        return "tombstone"

    operation = value.get("op")
    before = value.get("before")
    after = value.get("after")

    with _connect() as connection:
        with connection.cursor() as cursor:
            if topic == ROLE_TOPIC and after is not None:
                _upsert_role(cursor, after)
                return "upsert"
            if topic != USER_TOPIC:
                return "ignored"
            if operation == "d":
                if config.APPLY_DELETES and before is not None:
                    cursor.execute(
                        "delete from cdc_users where user_id = %s",
                        (before["user_id"],),
                    )
                    return "delete"
                return "ignored-delete"
            if after is not None:
                _upsert_user(cursor, after)
                return "upsert"
    return "ignored"


def consume(replay: bool = False, limit: int | None = None) -> dict[str, int]:
    group = config.CONSUMER_GROUP
    if replay:
        group = f"{group}-replay-{uuid.uuid4()}"
    consumer = Consumer(
        {
            "bootstrap.servers": "kafka:9092",
            "group.id": group,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([USER_TOPIC, ROLE_TOPIC])
    counts = {"upsert": 0, "delete": 0, "tombstone": 0, "ignored": 0}
    processed = 0
    idle = 0
    try:
        while True:
            message = consumer.poll(1.0)
            if message is None:
                idle += 1
                if idle >= 3:
                    break
                continue
            if message.error():
                # A topic that does not exist yet reports an error per poll.
                # The connector creates it on the first change.
                continue
            idle = 0
            raw = message.value()
            value = json.loads(raw) if raw else None
            outcome = apply_event(message.topic(), value)
            counts[outcome] = counts.get(outcome, 0) + 1
            consumer.commit(message=message, asynchronous=False)
            processed += 1
            if limit is not None and processed >= limit:
                break
    finally:
        consumer.close()
    return counts
