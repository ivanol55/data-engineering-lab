# Module 3 — Orchestration with Dagster

**Time:** 2–3 hours. **Profile:** `core` + `orchestration`.

## What you are building towards

So far you run scripts by hand. That works until a run fails at 02:00, a
backfill reads the wrong file, or someone asks "which tables are stale?" This
module turns the scripts into an asset graph that knows what depends on what,
which day it is processing, and whether the result is complete.

By the end you should have:

- assets for the three module 1 sources, the dbt models, and two asset checks;
- a daily partition keyed on the event date;
- a schedule that runs once a day in UTC;
- bounded retries on every asset;
- a backfill that changes only the partition you selected.

## Before you start

| Word | Plain meaning | In this module |
|---|---|---|
| **Orchestrator** | A service that runs tasks in order, on a schedule, and records what happened | Dagster |
| **Asset** | A thing the pipeline produces, such as a table | `raw_events`, `dbt_models` |
| **Dependency** | "B cannot run until A succeeds" | `dbt_models` depends on the three raw assets |
| **Partition** | One slice of the data, usually one day | `2026-09-03` |
| **Backfill** | Re-running history for one or more partitions | Materialise 2026-09-03 only |
| **Schedule** | A rule that starts a run at a time | Daily at 02:00 UTC |
| **Retry policy** | How many times a failed asset is retried, and how long to wait | Two retries, five seconds apart |
| **Asset check** | A test attached to an asset, run with it | Freshness and row count |
| **Idempotent** | Running it twice has the same effect as once | A retry must not duplicate rows |

The mental model is a factory shift:

- The **asset graph** is the bill of materials: which station feeds which.
- The **partition** is the work order for one day. A backfill is a work order
  for an old day, not "redo everything".
- The **schedule** is the shift start. If the shift clock and the work-order
  clock use different timezones, a day is skipped or repeated.
- The **asset check** is the quality gate at the end of the line. "The machine
  ran" is not "the box is full".

## Guided walkthrough

### Step 1 — Start the profile

```bash
make up P=core,orchestration
```

Open <http://localhost:3002>. The first build of the orchestration image takes
a few minutes; later starts reuse it.

**You should see:** the Dagster UI with the `module_03`, `ingestion`, and
`transform` asset groups.

### Step 2 — Materialise the fixture inventory

In the UI, open **Assets**, select `fixture_inventory`, and click
**Materialize**.

**You should see** metadata similar to:

```
event_files: 7
event_rows: 14000
intel_files: 7
intel_rows: 36
```

**What this proves:** the orchestrator can run a Python asset and record its
result. The run is stored in the `dagster` Postgres database, so it survives a
webserver restart.

### Step 3 — Materialise one day with the wrong config

Select `raw_events`, choose partition `2026-09-03`, and materialise it. Then
query the table:

```bash
make query Q='SELECT count(*), count(DISTINCT CAST(event_time AS date))
               FROM iceberg.raw.login_events'
```

**You should see:** `14000` events across `7` days, not `2000` events on one
day. `EVENT_PARTITION_MODE = "run_date"` ignores the partition key, so the
asset loads every file.

**What this proves:** a partition that is not passed to the loader is only a
label. The run is green; the data is wrong.

Reset the raw layer before the next step:

```bash
docker compose --profile tools run --rm tools \
  python modules/01-batch-ingestion/exercises/run.py reset
```

### Step 4 — Fix the config

Open `orchestration/config.py` and set:

| Setting | Wrong | Reference |
|---|---|---|
| `PARTITION_TIMEZONE` | `"America/New_York"` | `"UTC"` |
| `RETRY_MAX_ATTEMPTS` | `0` | `2` |
| `EVENT_PARTITION_MODE` | `"run_date"` | `"event_date"` |
| `ENABLE_ASSET_CHECKS` | `False` | `True` |

`SCHEDULE_CRON` is already `"0 2 * * *"`; it becomes correct once the timezone
is UTC.

Reload the code location in the UI (**Deployment → Reload code location**) so
Dagster imports the new values.

### Step 5 — Backfill the same partition

Materialise `raw_events` for `2026-09-03` again, then query:

```bash
make query Q='SELECT count(*), count(DISTINCT CAST(event_time AS date)),
                      min(CAST(event_time AS date)), max(CAST(event_time AS date))
               FROM iceberg.raw.login_events'
```

**You should see:** `2000`, `1`, `2026-09-03`, `2026-09-03`.

**What this proves:** the partition key reaches the loader. A backfill of one
day reads one file and touches one day.

### Step 6 — See the asset checks

With `ENABLE_ASSET_CHECKS = True`, the graph registers `events_freshness` and
`events_row_count` on `raw_events`. Materialise `2026-09-03` and open the run.

**You should see:** both checks pass, with metadata such as
`2000 events in 2026-09-03, expected ~2000`.

The checks are blocking: if a partition loads half a day, or if its newest
event is on another date, the run fails and `dbt_models` does not start. The
module check proves that by calling `freshness_result("2026-09-02")` after
loading only 2026-09-03; it must return a failed result. A partition with no
fixture file fails earlier, in `raw_events`, because the loader raises
`FileNotFoundError`.

### Step 7 — Run the check

```bash
make check M=3
```

**You should see:** seven passing tests. The check imports the graph directly,
asserts the UTC partition and the 02:00 schedule, materialises one partition,
and rejects a partition whose data is on another day.

## The choice, explained

| Setting | What it controls | Why the reference is right |
|---|---|---|
| `PARTITION_TIMEZONE = "UTC"` | The clock for partitions and the schedule | The ingestion cursor and fixtures are UTC; a local clock skips or repeats an hour at DST |
| `SCHEDULE_CRON = "0 2 * * *"` | When the daily run starts | 02:00 is after the daily fixture lands and before the working day |
| `RETRY_MAX_ATTEMPTS = 2` | How often a failed asset retries | Transient object-store or Trino errors recover; a bad key still fails quickly |
| `EVENT_PARTITION_MODE = "event_date"` | Whether the partition key reaches the loader | A backfill of 2026-09-03 must read the 2026-09-03 file, not today's |
| `ENABLE_ASSET_CHECKS = True` | Whether completeness checks run | "The job ran" is not "the partition is complete" |

**Why UTC.** The event timestamps and the fixture filenames are UTC. If the
partition clock is `America/New_York`, then on the DST change a "day" is 23 or
25 hours long, and the 02:00 run can land on the previous or next UTC date. The
schedule and the partition must share the cursor's clock.

**Why a bounded retry.** A retry is safe only if the asset is idempotent. These
assets are: module 1 merges on a key and the event load is incremental. Two
retries cover a transient network or object-store error without hiding a
persistent bug behind an infinite loop.

**Why `event_date`.** The asset calls
`run.py events --date <partition_key>`. With `run_date`, it calls
`run.py events` with no date, and the loader reads every file. A backfill then
rewrites history instead of one day.

**Why asset checks.** A row-count check with a 5% tolerance catches a partial
file; a freshness check catches a partition whose newest event is on a
different day. Both are blocking, so a failed check stops `dbt_models` instead
of letting a half-empty day reach the marts.

## Check yourself

<details>
<summary>What is the difference between an asset and an op?</summary>

An op is a step of computation. An asset is a durable thing the step produces,
with a name, dependencies, and often a partition. Other people depend on the
asset ("the `raw_events` table"), not on the Python function that builds it.

</details>

<details>
<summary>Why does a local schedule break a UTC cursor?</summary>

Because the schedule decides which date is "today" in local time, while the
loader and fixtures use UTC. Around a DST change the two dates disagree for an
hour, so a run can process the same day twice or skip one.

</details>

<details>
<summary>When is a retry unsafe?</summary>

When the asset is not idempotent. Retrying an append duplicates rows; retrying
a merge on a stable key is safe. Fix the asset before adding retries.

</details>

<details>
<summary>What does a backfill of one partition change?</summary>

Only the data for that partition, if the partition key reaches the loader. A
backfill must not re-read the world, and it must not rewrite other days.

</details>

<details>
<summary>What can an asset check prove that a container health check cannot?</summary>

That the data for this partition is complete and on the right date. A health
check only proves the process is running; a container can be healthy while the
partition is half-loaded.

</details>

## Useful commands

```bash
make up P=core,orchestration
open http://localhost:3002
docker compose --profile orchestration logs -f dagster-daemon
docker compose --profile orchestration exec dagster-webserver \
  dagster asset list -m orchestration.definitions
```

The `dagster` CLI runs inside the image, not on the host: the definitions
import Trino and dlt, which only exist in the container.

## Done when

- The asset graph materialises and appears in the Dagster UI.
- The daily graph runs end to end from a clean core profile.
- A forced failure stops downstream assets and shows a failed run.
- A one-day backfill changes only that day's partition.
- `make check M=3` fails on `main`, passes on `solutions`.

## Failure modes to watch

- **Partition ignored.** The run is green but loads every day. Check the row
  count and the distinct dates, not just the run status.
- **Local timezone.** The schedule fires at the right local time and the wrong
  UTC date.
- **Infinite retries.** A bad key hides behind a retry loop and the run never
  fails loudly.
- **Non-blocking checks.** A check that only warns lets a partial partition
  reach the marts.
- **Orchestrator as the pipeline.** Dagster calls the same module 1 and module
  2 code; it does not reimplement the load. Keep the logic in one place.

## Using AI on this module

Ask AI to explain Dagster partitions or to review a retry policy. Choose the
partition key and the clock yourself: they decide which day a backfill touches,
and a wrong answer looks green in the UI.
