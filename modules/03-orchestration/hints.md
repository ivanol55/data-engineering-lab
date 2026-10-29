# Module 3 — Orchestration with Dagster — hints

These are progressive hints, one per hard decision. Open one at a time.
The values live in `orchestration/config.py`.

<details>
<summary>Hint 1: Partition by event date</summary>

The partition key should describe the data, not the run. A backfill of `2026-09-03` must read `events-2026-09-03.jsonl` and nothing else. If your asset takes a run date and derives the file from it, you have coupled the schedule to the data.

`EVENT_PARTITION_MODE = "event_date"` makes `raw_events` pass
`context.partition_key` to the module 1 loader. `"run_date"` passes `None`,
which loads every fixture file.

</details>

<details>
<summary>Hint 2: Make retries safe first</summary>

Before adding a retry policy, run the asset twice by hand. If the second run changes row counts, a retry will hide the bug. Fix the key or the disposition, then add the retry.

`RETRY_MAX_ATTEMPTS = 2` is bounded. The asset's idempotency comes from
module 1 (merge on the natural key), not from the retry policy.

</details>

<details>
<summary>Hint 3: Pin the timezone</summary>

Use UTC everywhere: the cursor, the partition, and the schedule. If the schedule must be local, convert explicitly and test the DST boundary. A naive `datetime.now()` is a bug in this module.

Set `PARTITION_TIMEZONE = "UTC"`. The same value feeds
`DailyPartitionsDefinition` and the schedule's `execution_timezone`, so the
two cannot disagree.

</details>

<details>
<summary>Hint 4: Checks are part of the contract</summary>

Set `ENABLE_ASSET_CHECKS = True`. The freshness check compares the newest
event in the partition with the partition date; the row-count check compares
the count with `EXPECTED_EVENTS_PER_DAY` within `ROW_COUNT_TOLERANCE`. Both
block downstream materialisation.

</details>
