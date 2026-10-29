"""Behavioural checks for module 3.

The checks import the learner's Dagster definitions directly. That is the
contract: the graph must be loadable by the webserver and the daemon, and its
partitions must be honest about time.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from dagster import AssetKey, DagsterInstance, materialize

import checks.support as support
from orchestration import config
from orchestration.definitions import (
    daily_partitions,
    defs,
    freshness_result,
    raw_events,
    row_count_result,
)

ROOT = Path("/workspace")
RUN_M1 = ROOT / "modules" / "01-batch-ingestion" / "exercises" / "run.py"
PARTITION = "2026-09-03"


@pytest.fixture(scope="module", autouse=True)
def clean_raw_tables():
    support.run([sys.executable, str(RUN_M1), "reset"])
    yield


def _graph():
    return defs.resolve_asset_graph()


def test_graph_covers_ingestion_transform_and_checks():
    keys = {key.to_user_string() for key in _graph().get_all_asset_keys()}
    expected = {"raw_users", "raw_events", "raw_threat_intel", "dbt_models"}
    missing = expected - keys
    assert not missing, f"the asset graph is missing {sorted(missing)}"

    dbt_node = _graph().get(AssetKey("dbt_models"))
    parents = {key.to_user_string() for key in dbt_node.parent_keys}
    assert {"raw_users", "raw_events", "raw_threat_intel"} <= parents, (
        "dbt_models must depend on the three ingestion assets, not on a timer"
    )


def test_daily_partitions_are_utc_and_start_at_the_first_fixture():
    assert daily_partitions.get_first_partition_key() == "2026-09-01"
    assert daily_partitions.timezone == "UTC", (
        "the event cursor and the fixture dates are UTC; a local partition "
        "timezone moves a backfill around DST"
    )
    assert PARTITION in daily_partitions.get_partition_keys()


def test_schedule_runs_daily_in_utc():
    schedules = {schedule.name: schedule for schedule in defs.schedules}
    assert "daily_schedule" in schedules, "no schedule is attached to the graph"
    schedule = schedules["daily_schedule"]
    assert schedule.cron_schedule == "0 2 * * *", (
        f"expected one run per day at 02:00, got {schedule.cron_schedule!r}"
    )
    assert schedule.execution_timezone == "UTC", (
        "a local schedule against a UTC cursor skips or repeats an hour"
    )


def test_every_asset_has_a_bounded_retry_policy():
    graph = _graph()
    for name in ("raw_users", "raw_events", "raw_threat_intel", "dbt_models"):
        node = graph.get(AssetKey(name))
        policy = node.assets_def.op.retry_policy
        assert policy is not None, f"{name} has no retry policy"
        assert 1 <= policy.max_retries <= 5, (
            f"{name} retries {policy.max_retries} times; a bounded policy is "
            "needed so a bad key is not retried forever"
        )


def test_asset_checks_are_registered():
    check_keys = {
        key.name for key in _graph().asset_check_keys
    }
    assert {"events_freshness", "events_row_count"} <= check_keys, (
        "the graph needs a freshness check and a row-count check on raw_events"
    )


def test_one_day_backfill_loads_only_that_partition():
    result = materialize(
        [raw_events],
        partition_key=PARTITION,
        instance=DagsterInstance.ephemeral(),
        raise_on_error=True,
    )
    assert result.success, "materialising one partition failed"

    count, days, first_day, last_day = support.sql(
        "select count(*), count(distinct cast(event_time as date)), "
        "min(cast(event_time as date)), max(cast(event_time as date)) "
        "from iceberg.raw.login_events",
        schema="raw",
    )[0]
    assert count == 2000, (
        f"a one-day backfill loaded {count} events; it should load only the "
        f"{PARTITION} file"
    )
    assert days == 1 and str(first_day) == PARTITION and str(last_day) == PARTITION, (
        f"backfill leaked outside {PARTITION}: {first_day}..{last_day}"
    )


def test_asset_checks_reject_the_wrong_partition():
    assert row_count_result(PARTITION).passed, (
        "the row-count check rejects a complete partition"
    )
    assert not freshness_result("2026-09-02").passed, (
        "the freshness check accepts a partition whose newest event is on a "
        "different day"
    )
