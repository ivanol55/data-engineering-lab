"""Behavioural checks for module 2.

The check loads the module 1 raw tables, builds the dbt project twice, and
then asks the lakehouse questions a dashboard would ask: is the grain right,
does the intel join respect its validity window, is a re-run idempotent, and
does a late event survive the incremental cursor?
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from checks import support

ROOT = Path("/workspace")
RUN_M1 = ROOT / "modules" / "01-batch-ingestion" / "exercises" / "run.py"
RUN_M2 = ROOT / "modules" / "02-dbt-modelling" / "exercises" / "run.py"
DBT = ["dbt", "build", "--project-dir", "dbt", "--profiles-dir", "dbt"]


def _dbt(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(RUN_M2), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


@pytest.fixture(scope="module", autouse=True)
def loaded_lakehouse():
    support.run([sys.executable, str(RUN_M1), "reset"])
    support.run([sys.executable, str(RUN_M1), "all"])
    # dbt full-refreshes the marts in place. Dropping the schema would race
    # Lakekeeper's asynchronous purge worker: it can delete the new table's
    # metadata after the replacement has been committed.
    yield
    support.run([sys.executable, str(RUN_M1), "reset"])


def _build_or_fail(*args: str) -> None:
    result = _dbt(*args)
    assert result.returncode == 0, (
        "dbt build failed. The model runs, but the data does not satisfy its "
        "grain or its tests.\n"
        f"--- stdout ---\n{result.stdout[-8000:]}\n"
        f"--- stderr ---\n{result.stderr[-4000:]}"
    )


def test_fact_grain_is_one_row_per_event():
    _build_or_fail("build", "--full-refresh")

    total = support.scalar("select count(*) from iceberg.marts.fct_login_events")
    distinct = support.scalar(
        "select count(distinct event_id) from iceberg.marts.fct_login_events"
    )
    assert total == 14000, f"expected 14000 fact rows, got {total}"
    assert total == distinct, (
        f"fct_login_events has {total} rows but {distinct} event ids; the intel "
        "join or the incremental strategy changed the grain"
    )


def test_intel_join_respects_the_validity_window():
    # Give one day-seven event an indicator whose validity ended on day two.
    # An indicator-only join treats it as current; a validity-window join does
    # not. The fixture feed alone happens not to exercise this case.
    event_id, source_ip = support.sql(
        "select event_id, source_ip from iceberg.raw.login_events "
        "where event_time >= timestamp '2026-09-07 00:00:00 UTC' "
        "and source_ip not in (select indicator from iceberg.raw.threat_intel) "
        "limit 1",
        catalog="iceberg",
        schema="raw",
    )[0]
    support.sql(
        f"""
        insert into iceberg.raw.threat_intel (
            indicator, indicator_type, threat_type, confidence, severity,
            source, description, valid_from, valid_to, updated_at,
            generator_version, _dlt_load_id, _dlt_id
        ) values (
            '{source_ip}', 'ip', 'expired_test', 99, 'critical',
            'check', 'expired indicator used by the module 2 check',
            date '2026-09-01', date '2026-09-02',
            timestamp '2026-09-02 06:00:00 UTC', 'check', 'check', 'check-intel'
        )
        """,
        catalog="iceberg",
        schema="raw",
    )

    _build_or_fail("build", "--full-refresh")

    hits = support.scalar(
        "select count(*) from iceberg.marts.fct_login_events where intel_hit"
    )
    assert hits > 0, (
        "no event matched threat intel at all; the join is not running or the "
        "indicator key is wrong"
    )

    matched_expired = support.scalar(
        "select count(*) from iceberg.marts.fct_login_events "
        f"where event_id = '{event_id}' and intel_hit"
    )
    assert matched_expired == 0, (
        "an event on 2026-09-07 matched an indicator that expired on "
        "2026-09-02. Joining on indicator alone treats an expired indicator as "
        "current; constrain the join on event date and keep the latest "
        "revision inside its window."
    )

    outside = support.scalar(
        """
        select count(*)
        from iceberg.marts.fct_login_events
        where intel_hit
          and (
            cast(event_time as date) < intel_valid_from
            or (intel_valid_to is not null and cast(event_time as date) > intel_valid_to)
          )
        """
    )
    assert outside == 0, (
        f"{outside} fact rows carry an intel hit outside its valid_from/valid_to "
        "window. Joining on indicator alone treats an expired indicator as "
        "current; constrain the join on event date."
    )


def test_second_build_is_idempotent():
    _build_or_fail("build", "--full-refresh")
    before = support.scalar("select count(*) from iceberg.marts.fct_login_events")

    result = _dbt("build")
    assert result.returncode == 0, (
        "the second dbt build failed. An append incremental model doubles the "
        "last window; a merge on event_id is idempotent.\n"
        f"--- stdout ---\n{result.stdout[-8000:]}\n"
        f"--- stderr ---\n{result.stderr[-4000:]}"
    )

    after = support.scalar("select count(*) from iceberg.marts.fct_login_events")
    assert after == before, (
        f"a re-run changed the fact row count from {before} to {after}; "
        "check the incremental strategy and the unique key"
    )


def test_late_event_survives_the_cursor():
    _build_or_fail("build")

    support.sql(
        """
        insert into iceberg.raw.login_events (
            event_id, event_time, user_id, email, session_id, source_ip,
            country, city, latitude, longitude, device_id, device_type,
            operating_system, browser, auth_method, mfa_used, outcome,
            failure_reason, risk_score, is_attack, attack_type, attack_id,
            generator_version, _dlt_load_id, _dlt_id
        )
        select
            'late-event-0001', timestamp '2026-09-06 12:00:00 UTC',
            user_id, email, session_id, source_ip, country, city, latitude,
            longitude, device_id, device_type, operating_system, browser,
            auth_method, mfa_used, outcome, failure_reason, risk_score,
            is_attack, attack_type, attack_id, generator_version,
            'check', 'check-late'
        from iceberg.raw.login_events
        where event_time >= timestamp '2026-09-06 00:00:00 UTC'
          and event_time < timestamp '2026-09-07 00:00:00 UTC'
        limit 1
        """,
        catalog="iceberg",
        schema="raw",
    )

    _build_or_fail("build")
    found = support.scalar(
        "select count(*) from iceberg.marts.fct_login_events "
        "where event_id = 'late-event-0001'"
    )
    assert found == 1, (
        "a late event inside the two-day lookback never reached the fact table. "
        "The incremental cursor is too tight; late-arriving data is dropped."
    )


def test_user_delete_changes_the_dimension_not_history():
    _build_or_fail("build")

    user_id = support.scalar(
        "select user_id from iceberg.marts.fct_login_events "
        "where event_date = date '2026-09-01' limit 1"
    )
    assert user_id, "no day-one fact rows to test with"

    import psycopg

    with psycopg.connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "select account_status, updated_at, deleted_at from users "
                "where user_id = %s",
                (user_id,),
            )
            status, updated_at, deleted_at = cursor.fetchone()
            cursor.execute(
                "update users set deleted_at = now(), updated_at = now() "
                "where user_id = %s",
                (user_id,),
            )
        connection.commit()

    try:
        support.run([sys.executable, str(RUN_M1), "users"])
        _build_or_fail("build")

        is_deleted = support.scalar(
            "select is_deleted from iceberg.marts.dim_users "
            f"where user_id = '{user_id}'"
        )
        assert is_deleted is True, (
            "dim_users still shows the deleted user as active; the dimension "
            "did not pick up the source change"
        )

        history = support.scalar(
            "select user_is_deleted from iceberg.marts.fct_login_events "
            f"where user_id = '{user_id}' and event_date = date '2026-09-01' "
            "limit 1"
        )
        assert history is False, (
            "a day-one fact row changed when the user was deleted. The fact "
            "must keep the identity state observed at event time."
        )
    finally:
        with psycopg.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "update users set account_status = %s, updated_at = %s, "
                    "deleted_at = %s where user_id = %s",
                    (status, updated_at, deleted_at, user_id),
                )
            connection.commit()
