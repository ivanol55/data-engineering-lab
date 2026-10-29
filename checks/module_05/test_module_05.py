"""Behavioural checks for module 5."""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import psycopg
import pytest
import requests
from confluent_kafka import Consumer

import checks.support as support
from cdc import config
from cdc.consumer import ROLE_TOPIC, USER_TOPIC

ROOT = Path("/workspace")
RUN_CDC = ROOT / "cdc" / "run.py"
TEST_USER = "00000000-0000-0000-0000-000000009999"


def _connect():
    return psycopg.connect(host="postgres", dbname="app", user="app", password="app")


def _source_count() -> int:
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("select count(*) from users")
            return cursor.fetchone()[0]


def _target_count(table: str) -> int:
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"select count(*) from {table}")
            return cursor.fetchone()[0]


def _target_email(user_id: str):
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "select email from cdc_users where user_id = %s", (user_id,)
            )
            row = cursor.fetchone()
            return row[0] if row else None


@pytest.fixture(scope="module", autouse=True)
def snapshot():
    support.run([sys.executable, str(RUN_CDC), "reset"])
    support.run([sys.executable, str(RUN_CDC), "setup"])
    support.run([sys.executable, str(RUN_CDC), "consume"])
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("delete from users where user_id = %s", (TEST_USER,))
    yield
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("delete from users where user_id = %s", (TEST_USER,))
            cursor.execute("delete from cdc_users where user_id = %s", (TEST_USER,))


def test_connector_is_running_with_the_chosen_options():
    response = requests.get(
        f"{config.CONNECT_URL}/connectors/{config.CONNECTOR_NAME}/status",
        timeout=10,
    )
    response.raise_for_status()
    status = response.json()
    assert status["connector"]["state"] == "RUNNING"
    assert all(task["state"] == "RUNNING" for task in status["tasks"])

    config_response = requests.get(
        f"{config.CONNECT_URL}/connectors/{config.CONNECTOR_NAME}/config",
        timeout=10,
    )
    config_response.raise_for_status()
    connector_config = config_response.json()
    assert connector_config["snapshot.mode"] == "initial"
    assert "public.users" in connector_config["table.include.list"]
    assert "public.roles" in connector_config["table.include.list"]
    assert connector_config["tombstones.on.delete"] == "true"


def test_initial_snapshot_matches_the_source():
    assert _target_count("cdc_users") == _source_count(), (
        "the target does not match the source after the initial snapshot"
    )
    assert _target_count("cdc_roles") == 5, "roles were not captured"


def test_insert_update_and_delete_reach_the_target():
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("delete from users where user_id = %s", (TEST_USER,))
            cursor.execute(
                """
                insert into users (
                    user_id, email, full_name, role_id, account_status,
                    department, home_country, home_city, home_lat, home_lon,
                    mfa_enabled, created_at, updated_at
                ) values (
                    %s, 'cdc.test@acme.example', 'CDC Test', 1, 'active',
                    'Engineering', 'United States', 'New York', 40.7, -74.0,
                    true, now(), now()
                )
                """,
                (TEST_USER,),
            )
    support.run([sys.executable, str(RUN_CDC), "consume"])
    assert _target_email(TEST_USER) == "cdc.test@acme.example", (
        "the insert never reached the target"
    )

    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "update users set email = 'cdc.updated@acme.example', "
                "updated_at = now() where user_id = %s",
                (TEST_USER,),
            )
    support.run([sys.executable, str(RUN_CDC), "consume"])
    assert _target_email(TEST_USER) == "cdc.updated@acme.example", (
        "the update was ignored; the sink is not an upsert"
    )

    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("delete from users where user_id = %s", (TEST_USER,))
    support.run([sys.executable, str(RUN_CDC), "consume"])
    assert _target_email(TEST_USER) is None, (
        "the delete was ignored; the target still has the deleted user"
    )


def test_delete_emits_a_tombstone():
    consumer = Consumer(
        {
            "bootstrap.servers": "kafka:9092",
            "group.id": f"tombstone-check-{uuid.uuid4()}",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([USER_TOPIC, ROLE_TOPIC])
    tombstones = 0
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
                continue
            idle = 0
            if message.value() is None:
                tombstones += 1
    finally:
        consumer.close()
    assert tombstones >= 1, (
        "no null-value tombstone was emitted for the delete; a consumer "
        "cannot distinguish a delete from an empty record"
    )
