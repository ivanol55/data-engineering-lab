"""Dagster definitions for module 3.

The graph is deliberately small: three ingestion assets, one dbt asset, and
two asset checks. The interesting part is the partition key, the schedule
timezone, and the retry policy in ``config.py``.
"""

import subprocess
import sys
from datetime import date
from pathlib import Path

import trino
from dagster import (
    AssetCheckResult,
    AssetExecutionContext,
    AssetSelection,
    DailyPartitionsDefinition,
    Definitions,
    RetryPolicy,
    RunRequest,
    asset,
    asset_check,
    define_asset_job,
    schedule,
)

from orchestration import config

ROOT = Path("/workspace")
RUN_M1 = ROOT / "modules" / "01-batch-ingestion" / "exercises" / "run.py"
RUN_M2 = ROOT / "modules" / "02-dbt-modelling" / "exercises" / "run.py"

daily_partitions = DailyPartitionsDefinition(
    start_date="2026-09-01",
    timezone=config.PARTITION_TIMEZONE,
)

retry_policy = RetryPolicy(
    max_retries=config.RETRY_MAX_ATTEMPTS,
    delay=5,
)


def _run(script: Path, *args: str) -> str:
    result = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=900,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{script.name} {' '.join(args)} failed ({result.returncode})\n"
            f"--- stdout ---\n{result.stdout[-4000:]}\n"
            f"--- stderr ---\n{result.stderr[-4000:]}"
        )
    return result.stdout


def _run_m1(source: str, event_date: str | None = None) -> str:
    args = [source]
    if event_date is not None:
        args += ["--date", event_date]
    return _run(RUN_M1, *args)


def _trino_scalar(statement: str, schema: str = "raw"):
    connection = trino.dbapi.connect(
        host="trino",
        port=8080,
        user="lab",
        catalog="iceberg",
        schema=schema,
    )
    try:
        cursor = connection.cursor()
        cursor.execute(statement)
        rows = cursor.fetchall()
        return rows[0][0] if rows else None
    finally:
        connection.close()


@asset(group_name="module_03", compute_kind="python")
def fixture_inventory() -> dict[str, int]:
    """Count the deterministic fixtures the batch path depends on."""
    events = sorted((ROOT / "fixtures" / "events").glob("*.jsonl"))
    intel = sorted((ROOT / "fixtures" / "threat_intel").glob("*.jsonl"))
    events_rows = sum(1 for path in events for _ in path.open(encoding="utf-8"))
    intel_rows = sum(1 for path in intel for _ in path.open(encoding="utf-8"))
    return {
        "event_files": len(events),
        "event_rows": events_rows,
        "intel_files": len(intel),
        "intel_rows": intel_rows,
    }


@asset(
    group_name="ingestion",
    compute_kind="python",
    partitions_def=daily_partitions,
    retry_policy=retry_policy,
)
def raw_users(context: AssetExecutionContext) -> None:
    output = _run_m1("users")
    context.log.info(output[-2000:])


@asset(
    group_name="ingestion",
    compute_kind="python",
    partitions_def=daily_partitions,
    retry_policy=retry_policy,
)
def raw_events(context: AssetExecutionContext) -> None:
    event_date = (
        context.partition_key
        if config.EVENT_PARTITION_MODE == "event_date"
        else None
    )
    output = _run_m1("events", event_date)
    context.log.info(output[-2000:])


@asset(
    group_name="ingestion",
    compute_kind="python",
    partitions_def=daily_partitions,
    retry_policy=retry_policy,
)
def raw_threat_intel(context: AssetExecutionContext) -> None:
    output = _run_m1("threat-intel")
    context.log.info(output[-2000:])


@asset(
    group_name="transform",
    compute_kind="dbt",
    partitions_def=daily_partitions,
    deps=[raw_users, raw_events, raw_threat_intel],
    retry_policy=retry_policy,
)
def dbt_models(context: AssetExecutionContext) -> None:
    output = _run(RUN_M2, "build")
    context.log.info(output[-4000:])


def freshness_result(partition_key: str) -> AssetCheckResult:
    """The partition's newest event must fall on the partition date."""
    max_event_time = _trino_scalar(
        "select max(event_time) from iceberg.raw.login_events "
        f"where cast(event_time as date) = date '{partition_key}'"
    )
    if max_event_time is None:
        return AssetCheckResult(
            passed=False,
            description=f"no events loaded for {partition_key}",
        )
    age_hours = (
        max_event_time.date() - date.fromisoformat(partition_key)
    ).total_seconds() / 3600
    return AssetCheckResult(
        passed=abs(age_hours) <= config.FRESHNESS_MAX_HOURS,
        description=f"newest event in partition {partition_key} is {max_event_time}",
        metadata={"max_event_time": str(max_event_time)},
    )


def row_count_result(partition_key: str) -> AssetCheckResult:
    """A partition with half a day of events is not a successful run."""
    count = _trino_scalar(
        "select count(*) from iceberg.raw.login_events "
        f"where cast(event_time as date) = date '{partition_key}'"
    ) or 0
    expected = config.EXPECTED_EVENTS_PER_DAY
    tolerance = config.ROW_COUNT_TOLERANCE
    lower = expected * (1 - tolerance)
    upper = expected * (1 + tolerance)
    return AssetCheckResult(
        passed=lower <= count <= upper,
        description=f"{count} events in {partition_key}, expected ~{expected}",
        metadata={"row_count": int(count), "expected": int(expected)},
    )


asset_checks = []
if config.ENABLE_ASSET_CHECKS:

    @asset_check(asset=raw_events, blocking=True)
    def events_freshness(context: AssetExecutionContext) -> AssetCheckResult:
        return freshness_result(context.partition_key)

    @asset_check(asset=raw_events, blocking=True)
    def events_row_count(context: AssetExecutionContext) -> AssetCheckResult:
        return row_count_result(context.partition_key)

    asset_checks = [events_freshness, events_row_count]


daily_job = define_asset_job(
    "daily_refresh",
    selection=AssetSelection.assets(
        raw_users, raw_events, raw_threat_intel, dbt_models
    ),
)


@schedule(
    job=daily_job,
    cron_schedule=config.SCHEDULE_CRON,
    execution_timezone=config.PARTITION_TIMEZONE,
)
def daily_schedule(context):
    partition = context.scheduled_execution_time.date().isoformat()
    return RunRequest(partition_key=partition, run_config={})


defs = Definitions(
    assets=[fixture_inventory, raw_users, raw_events, raw_threat_intel, dbt_models],
    asset_checks=asset_checks,
    schedules=[daily_schedule],
)
