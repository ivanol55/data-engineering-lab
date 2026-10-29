"""Module 5 entry point.

Usage:
    python cdc/run.py reset
    python cdc/run.py setup
    python cdc/run.py consume
    python cdc/run.py consume --replay
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import psycopg
from confluent_kafka.admin import AdminClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cdc import config, connector  # noqa: E402
from cdc.consumer import ROLE_TOPIC, USER_TOPIC, consume  # noqa: E402

CREATE_USERS = """
create table if not exists cdc_users (
    user_id uuid primary key,
    email text,
    full_name text,
    role_id integer,
    account_status text,
    department text,
    home_country text,
    home_city text,
    mfa_enabled boolean,
    created_at timestamptz,
    updated_at timestamptz,
    deleted_at timestamptz
)
"""

CREATE_ROLES = """
create table if not exists cdc_roles (
    role_id integer primary key,
    name text,
    description text
)
"""


def _connect():
    return psycopg.connect(
        host="postgres", dbname="app", user="app", password="app", autocommit=True
    )


def _drop_topics() -> None:
    names = [USER_TOPIC, ROLE_TOPIC, config.SCHEMA_HISTORY_TOPIC]
    admin = AdminClient({"bootstrap.servers": "kafka:9092"})
    futures = admin.delete_topics(names)
    for future in futures.values():
        try:
            future.result(timeout=10)
        except Exception:
            pass
    # Topic deletion is asynchronous. Re-registering the connector before the
    # old schema-history topic is gone makes Debezium read a stale LSN.
    for _ in range(60):
        topics = admin.list_topics(timeout=10).topics
        if not any(name in topics for name in names):
            return
        time.sleep(1)
    raise RuntimeError(f"topics were not deleted: {names}")


def _wait_for_slot(timeout: int = 60) -> None:
    """The connector deletes asynchronously; wait for its slot to go idle."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        with _connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "select active_pid from pg_replication_slots "
                    "where slot_name = %s",
                    (config.SLOT_NAME,),
                )
                row = cursor.fetchone()
        if row is None or row[0] is None:
            return
        time.sleep(1)
    raise RuntimeError(f"replication slot {config.SLOT_NAME} is still active")


def reset() -> None:
    connector.delete()
    _wait_for_slot()
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("drop table if exists cdc_users")
            cursor.execute("drop table if exists cdc_roles")
            cursor.execute(
                "select pg_drop_replication_slot(slot_name) "
                "from pg_replication_slots where slot_name = %s",
                (config.SLOT_NAME,),
            )
            cursor.execute(
                "drop publication if exists " + config.PUBLICATION_NAME
            )
    _drop_topics()
    print("deleted connector, slot, publication, target tables and topics")


def setup() -> None:
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(CREATE_USERS)
            cursor.execute(CREATE_ROLES)
    connector.register()
    status = connector.wait_running()
    print(f"connector {config.CONNECTOR_NAME}: {status['connector']['state']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["reset", "setup", "consume"])
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    if args.command == "reset":
        reset()
    elif args.command == "setup":
        setup()
    else:
        print(consume(replay=args.replay, limit=args.limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
