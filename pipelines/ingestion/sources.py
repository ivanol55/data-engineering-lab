"""dlt resources for the three module 1 sources."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

import dlt
import psycopg
from dlt.destinations.impl.filesystem.iceberg_adapter import iceberg_adapter

from de_lab_generator.model import EVENT_COLUMNS, THREAT_INTEL_COLUMNS

from . import config


def _jsonl_rows(directory: Path, event_date: str | None = None) -> Iterator[dict]:
    if event_date is None:
        files = sorted(directory.glob("*.jsonl"))
    else:
        candidate = directory / f"events-{event_date}.jsonl"
        if not candidate.exists():
            raise FileNotFoundError(
                f"no fixture for {event_date}: {candidate} does not exist. "
                "Run `make fixtures` first."
            )
        files = [candidate]
    if not files:
        raise FileNotFoundError(
            f"no JSONL files in {directory}. Run `make fixtures` first."
        )
    for path in files:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc


def fetch_users() -> Iterator[dict]:
    query = """
        SELECT user_id::text AS user_id,
               email,
               full_name,
               role_id,
               account_status,
               department,
               home_country,
               home_city,
               home_lat,
               home_lon,
               mfa_enabled,
               created_at,
               updated_at,
               last_login_at,
               deleted_at
          FROM users
         ORDER BY user_id
    """
    with psycopg.connect() as connection:
        with connection.cursor(row_factory=psycopg.rows.dict_row) as cursor:
            cursor.execute(query)
            for row in cursor:
                if config.DELETION_POLICY == "hard_delete":
                    if row["deleted_at"] is not None:
                        continue
                    row["is_deleted"] = False
                elif config.DELETION_POLICY == "soft_delete":
                    row["is_deleted"] = row["deleted_at"] is not None
                else:
                    # TODO(learner): with policy "TODO" every user looks alive.
                    row["is_deleted"] = False
                yield row


def users_resource():
    disposition = (
        "replace"
        if config.DELETION_POLICY == "hard_delete"
        else config.USERS_WRITE_DISPOSITION
    )

    @dlt.resource(
        name="users",
        table_format="iceberg",
        write_disposition=disposition,
        primary_key=config.USERS_PRIMARY_KEY,
        columns=config.USER_COLUMNS,
    )
    def users():
        yield list(fetch_users())

    return users


def events_resource(event_date: str | None = None):
    kwargs = {
        "name": "login_events",
        "table_format": "iceberg",
        "write_disposition": "append",
        "columns": EVENT_COLUMNS,
    }
    if config.EVENTS_INCREMENTAL:
        kwargs["incremental"] = dlt.sources.incremental("event_time")

    @dlt.resource(**kwargs)
    def login_events():
        yield from _jsonl_rows(config.EVENTS_DIR, event_date=event_date)

    if config.EVENTS_PARTITION is not None:
        return iceberg_adapter(login_events, partition=config.EVENTS_PARTITION)
    return login_events


def threat_intel_resource():
    @dlt.resource(
        name="threat_intel",
        table_format="iceberg",
        write_disposition=config.THREAT_INTEL_WRITE_DISPOSITION,
        primary_key=config.THREAT_INTEL_PRIMARY_KEY,
        columns=THREAT_INTEL_COLUMNS,
    )
    def threat_intel():
        rows = list(_jsonl_rows(config.THREAT_INTEL_DIR))
        keys = config.THREAT_INTEL_PRIMARY_KEY
        if keys:
            # PyIceberg's upsert rejects duplicate keys inside one load
            # package. The feed revises the same indicator on later days, so
            # keep the newest payload per natural key before loading.
            keys = [keys] if isinstance(keys, str) else list(keys)
            latest: dict[tuple, dict] = {}
            for row in rows:
                key = tuple(row.get(k) for k in keys)
                current = latest.get(key)
                if current is None or str(row.get("updated_at")) >= str(current.get("updated_at")):
                    latest[key] = row
            rows = list(latest.values())
        yield rows

    return threat_intel


RESOURCES = {
    "users": users_resource,
    "events": events_resource,
    "threat-intel": threat_intel_resource,
}
