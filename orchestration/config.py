"""Module 3 learner decisions.

Dagster loads these values when it imports ``definitions.py``. Change one
value, restart the orchestration profile, and run ``make check M=3``. The
graph still runs with the wrong values; it just runs at the wrong time, or
loads the wrong partition.
"""

# TODO(learner): the ingestion cursor is UTC and the fixtures are keyed by
# UTC date. A local timezone moves the partition around DST. Use "UTC".
PARTITION_TIMEZONE = "UTC"

# TODO(learner): run once a day, after the daily fixture is expected to land.
# The reference is 02:00 in PARTITION_TIMEZONE.
SCHEDULE_CRON = "0 2 * * *"

# TODO(learner): a transient object-store or Trino error should be retried,
# but a bad key must not be retried forever. The reference is two retries.
RETRY_MAX_ATTEMPTS = 2

# TODO(learner): "run_date" derives the file from the wall clock, so a backfill
# of 2026-09-03 reads today's file. Use "event_date" and pass the partition
# key to the module 1 loader.
EVENT_PARTITION_MODE = "event_date"

# TODO(learner): asset checks are the difference between "the job ran" and
# "the partition is complete". Turn them on.
ENABLE_ASSET_CHECKS = True

# The fixtures contain 2,000 events per day. A row-count check allows a small
# tolerance for late-arriving events.
EXPECTED_EVENTS_PER_DAY = 2000
ROW_COUNT_TOLERANCE = 0.05

# Freshness is measured against the partition being materialised, not against
# wall-clock time: the fixtures are historical and must stay reproducible.
FRESHNESS_MAX_HOURS = 24
