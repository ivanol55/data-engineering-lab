"""Behavioural checks for module 1.

These tests exercise the learner's pipeline as a black box: reset the
lakehouse, run the CLI, inspect the Iceberg tables. They fail on `main`
because the module 1 decisions are still TODO.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from . import helpers


@pytest.fixture(autouse=True)
def clean_lakehouse():
    helpers.reset()
    yield
    helpers.reset()


def _load(*commands: str) -> None:
    helpers.run_pipeline(*commands)


def test_users_are_a_current_snapshot():
    user_id = "00000000-0000-0000-0000-000000000001"
    original = _current_user(user_id)
    try:
        helpers.postgres(
            "UPDATE users SET account_status = 'suspended', updated_at = now() "
            "WHERE user_id = %s",
            (user_id,),
        )
        _load("users")
        _load("users")

        table_rows = helpers.rows("users")
        ids = [row["user_id"] for row in table_rows]
        assert len(ids) == len(set(ids)), "users contains duplicate user_id values"
        assert len(ids) == 2000, f"expected 2000 users, got {len(ids)}"

        changed = [row for row in table_rows if row["user_id"] == user_id]
        assert len(changed) == 1, "the changed user appears more than once"
        assert changed[0]["account_status"] == "suspended", (
            "the second run did not replace the old user row; check the primary "
            "key and write disposition"
        )
    finally:
        helpers.postgres(
            "UPDATE users SET account_status = %s, updated_at = %s WHERE user_id = %s",
            (original["account_status"], original["updated_at"], user_id),
        )


def test_deleted_users_follow_the_configured_policy():
    policy = helpers.config.DELETION_POLICY
    assert policy in {"soft_delete", "hard_delete"}, (
        f"DELETION_POLICY is {policy!r}; choose 'soft_delete' or 'hard_delete' "
        "in pipelines/ingestion/config.py"
    )

    user_id = "00000000-0000-0000-0000-000000000003"
    original = _current_user(user_id)
    try:
        helpers.postgres(
            "UPDATE users SET deleted_at = now(), updated_at = now() WHERE user_id = %s",
            (user_id,),
        )
        _load("users")

        table_rows = helpers.rows("users")
        matched = [row for row in table_rows if row["user_id"] == user_id]
        if policy == "soft_delete":
            assert len(matched) == 1, "soft delete must keep the row"
            assert matched[0]["is_deleted"] is True, (
                "soft-deleted user is still marked is_deleted=false"
            )
        else:
            assert matched == [], "hard delete must remove the user row"
    finally:
        helpers.postgres(
            "UPDATE users SET deleted_at = NULL, account_status = %s, updated_at = %s "
            "WHERE user_id = %s",
            (original["account_status"], original["updated_at"], user_id),
        )


def test_events_backfill_is_incremental_and_partitioned(tmp_path):
    extra = helpers.config.EVENTS_DIR / "events-2026-09-08.jsonl"
    extra.unlink(missing_ok=True)

    base_files = helpers.fixture_event_files()
    base_count = helpers.count_jsonl(base_files)

    _load("events")
    first = helpers.rows("login_events")
    assert len(first) == base_count, (
        f"first load should contain {base_count} events, got {len(first)}"
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "de_lab_generator",
            "events",
            "--start",
            "2026-09-08",
            "--days",
            "1",
            "--events-per-day",
            "2000",
            "--attack-mix",
            "0.08",
            "--out",
            str(helpers.config.EVENTS_DIR),
        ],
        cwd=helpers.ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert extra.exists(), "generator did not write the extra day"

    try:
        _load("events")
        second = helpers.rows("login_events")
        ids = [row["event_id"] for row in second]
        assert len(ids) == len(set(ids)), "duplicate event_id after the second load"
        assert len(second) == base_count + 2000, (
            "the second load must add only the new day. "
            f"expected {base_count + 2000} rows, got {len(second)}. "
            "Check EVENTS_INCREMENTAL."
        )

        assert _partitioned_by_day(), (
            "login_events is not partitioned by day(event_time); "
            "check EVENTS_PARTITION"
        )
    finally:
        extra.unlink(missing_ok=True)


def test_threat_intel_revisions_replace_older_rows():
    expected = helpers.expected_threat_intel()

    _load("threat-intel")
    first = helpers.rows("threat_intel")

    keys = [(row["indicator"], str(row["valid_from"])) for row in first]
    assert len(keys) == len(set(keys)), (
        "threat_intel contains duplicate (indicator, valid_from) keys; "
        "check the composite primary key and merge disposition"
    )
    assert len(first) == len(expected), (
        f"expected {len(expected)} current indicators, got {len(first)}"
    )

    actual = {(row["indicator"], str(row["valid_from"])): row for row in first}
    for key, wanted in expected.items():
        assert key in actual, f"missing indicator {key}"
        assert int(actual[key]["confidence"]) == int(wanted["confidence"]), (
            f"indicator {key} kept the stale revision"
        )

    _load("threat-intel")
    second = helpers.rows("threat_intel")
    assert len(second) == len(expected), "a re-run duplicated threat-intel rows"


def _current_user(user_id: str) -> dict:
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                "SELECT account_status, updated_at FROM users WHERE user_id = %s",
                (user_id,),
            )
            return cursor.fetchone()


def _partitioned_by_day() -> bool:
    table = helpers.table("login_events")
    schema = table.schema()
    spec = table.spec()
    for field in spec.fields:
        source = schema.find_field(field.source_id)
        if source.name == "event_time" and str(field.transform) == "day":
            return True
    return False
