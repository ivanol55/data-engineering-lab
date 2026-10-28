# Module 3 — Orchestration with Dagster — hints

These are progressive hints, one per hard decision. Open one at a time.

> This module is a scaffold: the exercises and checks are not implemented
> yet. The hints describe the decisions the module will test.

<details>
<summary>Hint 1: Partition by event date</summary>

The partition key should describe the data, not the run. A backfill of `2026-09-03` must read `events-2026-09-03.jsonl` and nothing else. If your asset takes a run date and derives the file from it, you have coupled the schedule to the data.

</details>

<details>
<summary>Hint 2: Make retries safe first</summary>

Before adding a retry policy, run the asset twice by hand. If the second run changes row counts, a retry will hide the bug. Fix the key or the disposition, then add the retry.

</details>

<details>
<summary>Hint 3: Pin the timezone</summary>

Use UTC everywhere: the cursor, the partition, and the schedule. If the schedule must be local, convert explicitly and test the DST boundary. A naive `datetime.now()` is a bug in this module.

</details>
