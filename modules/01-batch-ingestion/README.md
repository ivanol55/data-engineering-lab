# Module 1 — Batch ingestion into Iceberg

**Time:** 2–3 hours. **Profile:** `core` + `tools`.

## What you are building towards

The rest of the course reads three raw tables. This module puts them there:

| Source | Shape | Target table | What a correct table looks like |
|---|---|---|---|
| Postgres `users` + `roles` | 2,000-row mutable snapshot | `iceberg.raw.users` | one row per user, current values, deletion policy applied |
| Generated login events | 7 daily JSONL files, 2,000 events each | `iceberg.raw.login_events` | only new days appended, no duplicate `event_id`, partitioned by day |
| Daily threat intel | 7 JSONL files with revised indicators | `iceberg.raw.threat_intel` | one row per `(indicator, valid_from)`, newest revision wins |

Everything downstream depends on these three tables. If a user appears twice
here, module 2 counts them twice, module 7 scores the wrong account, and module
9 trains on duplicated history. Raw does not mean careless.

The pipeline is dlt → filesystem destination → Lakekeeper → SeaweedFS. Trino
and pyiceberg read the same tables.

## Before you start

You need these words for this module. The full list is in
[`docs/GLOSSARY.md`](../../docs/GLOSSARY.md).

| Word | Plain meaning | In this module |
|---|---|---|
| **Ingestion** | Copying data from a source into the lakehouse | Postgres and the JSONL files become Iceberg tables |
| **Raw layer** | The first copy, close to the source | `iceberg.raw.*` |
| **Snapshot** | The full current state of a table | The 2,000 users |
| **Append** | Add rows without checking for duplicates | Running the load twice doubles the table |
| **Merge / upsert** | Replace the row with the same key, insert it if new | One row per `user_id` after any number of runs |
| **Primary key** | The column or columns that identify one row | `user_id`; `(indicator, valid_from)` |
| **Idempotent** | Running it twice has the same effect as running it once | A merge on a stable key |
| **Cursor / incremental** | A bookmark saying "already loaded up to here" | `event_time` for login events |
| **Partition** | A physical split of a table, usually by day | `day(event_time)` |
| **Grain** | What one row means | "One row per login event" |
| **Late data** | An event whose timestamp is older than data already loaded | A backfill for an earlier day |

The mental model is a photocopier:

- **Append** is photocopying the whole personnel file every morning and putting
  the new copy on top. After a week you have seven copies of every page, and
  the oldest copy still says the person is active.
- **Merge** is replacing only the pages that changed. The file still has one
  page per person.
- **A cursor** is a bookmark. Without it, you photocopy the whole file again.
- **A partition** is a folder per day. It lets you throw away old days without
  reading the rest.

A pipeline that runs without an error is not the same as a pipeline that is
correct. The values in this module are chosen so the pipeline runs and produces
plausible, wrong tables. Your job is to make the tables trustworthy.

## Guided walkthrough

Follow the steps in order. Do not fix the config yet; first see the bug.

### Step 1 — Load the three sources

```bash
make up P=core
make load
```

**You should see**, at the end:

```
Pipeline ingestion load step finished in 1.79 seconds
1 load package(s) were loaded to destination filesystem and into dataset raw
The filesystem destination used s3://lakehouse/warehouse location to store data
Load package 1793320520.6543498 is LOADED and contains no failed jobs
raw.users: 2000 rows
raw.login_events: 14000 rows
raw.threat_intel: 36 rows
```

The load package id and timings will differ. The row counts should not.

**What this proves:** dlt can read all three sources and write Iceberg tables
through Lakekeeper. It does not prove the write semantics are right.

### Step 2 — Inspect the tables

```bash
make query Q='SELECT count(*) FROM iceberg.raw.users'
make query Q='SELECT count(*) FROM iceberg.raw.login_events'
make query Q='SELECT count(*) FROM iceberg.raw.threat_intel'
```

**You should see:** `2000`, `14000`, and `36`.

The threat-intel feed has 36 rows but only 24 distinct
`(indicator, valid_from)` keys: the same indicator is revised on later days.
That difference is the lesson of step 4.

### Step 3 — Run the load again and watch it break

```bash
make load
make query Q='SELECT count(*) FROM iceberg.raw.users'
make query Q='SELECT count(*) FROM iceberg.raw.login_events'
make query Q='SELECT count(*) FROM iceberg.raw.threat_intel'
```

**You should see:** `4000`, `28000`, and `72`. The second load appended a
second copy of everything.

**What this proves:** the current config is not idempotent. Nothing failed, no
alert fired, and every query still returns a number. This is the silent failure
the module is about.

### Step 4 — Reset the raw layer

```bash
docker compose --profile tools run --rm tools \
  python modules/01-batch-ingestion/exercises/run.py reset
make load
```

**You should see** the counts from step 1 again: `2000`, `14000`, `36`.

`run.py reset` deletes the `raw` dataset and the dlt state. `make reset`
deletes the whole lab, including Postgres; you do not need that here.

### Step 5 — Make the three decisions

Open `pipelines/ingestion/config.py`. The `TODO(learner)` comments mark the
values to change. Use the reference answers in “The choice, explained” below,
change one group at a time, and re-run the load.

After each change, reset and load again so the old duplicate rows do not hide
the new behaviour:

```bash
docker compose --profile tools run --rm tools \
  python modules/01-batch-ingestion/exercises/run.py reset
make load
```

### Step 6 — Verify the partition and the re-run

```bash
make query Q='SELECT * FROM iceberg.raw."login_events$partitions"'
make load
make query Q='SELECT count(*) FROM iceberg.raw.login_events'
```

**You should see:** a partition row with `day(event_time)`, and `14000` after
the second load, not `28000`.

### Step 7 — Run the check

```bash
make check M=1
```

**You should see:** four passing tests. The check resets the raw layer between
scenarios, so it is safe to run repeatedly.

## The choice, explained

Every value below is wrong on `main` and correct on `solutions`. The goal is
not to guess the string; it is to know what breaks when it is wrong.

| Setting | Wrong default | Reference | Why |
|---|---|---|---|
| `USERS_PRIMARY_KEY` | `None` | `"user_id"` | A merge needs a key; without one, dlt can only append |
| `USERS_WRITE_DISPOSITION` | `"append"` | `"merge"` | Postgres is mutable; the lakehouse must keep one row per user |
| `DELETION_POLICY` | `"TODO"` | `"soft_delete"` | Deleted users must be marked, not silently kept active |
| `EVENTS_INCREMENTAL` | `False` | `True` | A re-run must load only new days, not the whole history |
| `EVENTS_PARTITION` | `None` | `iceberg_partition.day("event_time")` | Date filters and retention should skip whole files |
| `THREAT_INTEL_PRIMARY_KEY` | `None` | `["indicator", "valid_from"]` | An indicator revision is identified by both columns |
| `THREAT_INTEL_WRITE_DISPOSITION` | `"append"` | `"merge"` | A revised indicator must replace the old revision |

**Users: primary key + merge.** Postgres is the system of record and its rows
change. A full snapshot is easy to extract, but appending it duplicates every
user and freezes old statuses. `merge` on `user_id` replaces the changed row and
keeps the table at 2,000 rows. The check changes one user's status, loads twice,
and asserts that the user appears once with the new status.

**Users: deletion policy.** `deleted_at` is set for 42 seeded users. There are
two defensible answers:

- `soft_delete` keeps the row and sets `is_deleted = true`. Downstream can still
  join the user and can tell that the account was deleted. This preserves
  history and is the reference.
- `hard_delete` drops the row and rewrites the snapshot. Simpler for consumers,
  but a historical login event loses the identity it pointed at.

`"TODO"` keeps every deleted user looking active. That is a security bug, not a
formatting choice: a deleted account can still receive a risk score.

**Events: incremental cursor.** The cursor is `event_time`. On each run dlt
loads only events newer than the last loaded timestamp. Without it, every run
appends all 14,000 rows again. The cursor is not a watermark for late data: an
event that arrives with an old timestamp is skipped. Module 3 fixes that for
orchestrated backfills; module 6 uses a real streaming watermark. For this
batch load, accept the limitation and load files in day order.

**Events: daily partition.** `iceberg_partition.day("event_time")` makes
`WHERE event_time >= ...` prune files and makes retention a metadata operation.
The trade-off is more, smaller files if you load tiny batches. Partition by the
column you filter and expire on, not by the load date.

**Threat intel: composite key + merge.** The feed revises earlier indicators:
the same `(indicator, valid_from)` appears again with a higher confidence. An
append keeps both revisions, and a join on `indicator` then double-counts every
matching event. A merge keeps the newest payload per key. dlt's Iceberg upsert
also rejects duplicate keys inside one load package, so the resource keeps the
latest revision per key before loading.

## Check yourself

Try to answer before opening the detail.

<details>
<summary>Why is an append of a full users snapshot wrong even if the row count looks plausible?</summary>

Because the same logical user now has several rows, one per snapshot. A
dashboard that counts users doubles, a join to events fans out, and the oldest
row still says `active` after the account was disabled. The row count only looks
plausible until you compare it with the source.

</details>

<details>
<summary>What exactly does the cursor skip?</summary>

An event whose `event_time` is not newer than the highest `event_time` already
loaded. That includes a late event for an earlier day, and a same-timestamp
event that arrives after the load. The cursor is a high-water mark, not a
complete record of what has been seen.

</details>

<details>
<summary>Why does the threat-intel feed need `(indicator, valid_from)` and not just `indicator`?</summary>

The same indicator can have several validity windows. `valid_from` separates
them. Using `indicator` alone would merge two different periods into one row and
lose the history that module 2's validity join needs.

</details>

<details>
<summary>What would you check to prove the load is idempotent?</summary>

Run it twice and compare row counts and primary-key uniqueness. The module 1
check does exactly that: it loads users twice, loads events twice, and loads
threat intel twice, then asserts one row per key.

</details>

<details>
<summary>Why partition by `event_time` and not by the load date?</summary>

Queries filter by when the login happened, not by when you happened to load it.
A backfill of 2026-09-03 belongs in the 2026-09-03 partition even if it runs
today. Partitioning by load date makes backfills land in the wrong file and
breaks retention.

</details>

## Table contracts

`raw.users`

```
user_id text, email text, full_name text, role_id bigint, account_status text,
department text, home_country text, home_city text, home_lat double,
home_lon double, mfa_enabled boolean, created_at timestamptz,
updated_at timestamptz, last_login_at timestamptz, deleted_at timestamptz,
is_deleted boolean, _dlt_load_id text, _dlt_id text
```

`raw.login_events`

```
event_id text, event_time timestamptz, user_id text, email text,
session_id text, source_ip text, country text, city text, latitude double,
longitude double, device_id text, device_type text, operating_system text,
browser text, auth_method text, mfa_used boolean, outcome text,
failure_reason text, risk_score bigint, is_attack boolean, attack_type text,
attack_id text, generator_version text, _dlt_load_id text, _dlt_id text
```

`raw.threat_intel`

```
indicator text, indicator_type text, threat_type text, confidence bigint,
severity text, source text, description text, valid_from date, valid_to date,
updated_at timestamptz, generator_version text, _dlt_load_id text, _dlt_id text
```

`_dlt_load_id` and `_dlt_id` are dlt bookkeeping columns. Do not remove them;
the checks and later modules expect them.

## Useful queries

```bash
make query Q='SELECT count(*), count(DISTINCT user_id) FROM iceberg.raw.users'
make query Q='SELECT count(*), count(DISTINCT event_id) FROM iceberg.raw.login_events'
make query Q="SELECT date_trunc('day', event_time) d, count(*) FROM iceberg.raw.login_events GROUP BY 1 ORDER BY 1"
make query Q='SELECT attack_type, count(*) FROM iceberg.raw.login_events WHERE is_attack GROUP BY 1 ORDER BY 2 DESC'
make query Q='SELECT count(*), count(DISTINCT (indicator, valid_from)) FROM iceberg.raw.threat_intel'
```

DuckDB can read the same tables:

```bash
make duckdb Q='SELECT outcome, count(*) FROM login_events GROUP BY 1'
```

## Done when

- `make load` finishes with no failed jobs.
- `make query Q='SELECT count(*) FROM iceberg.raw.users'` returns 2,000.
- `make query Q='SELECT count(*) FROM iceberg.raw.login_events'` returns
  14,000 (or 16,000 after the checks add a day).
- `raw.login_events` shows `partitioning = ARRAY['day(event_time)']`.
- A second `make load` does not change any count.
- `make check M=1` passes.

## Failure modes to watch

- **Append instead of merge** → counts double on the second run.
- **No incremental cursor** → the whole history is re-loaded.
- **No deletion handling** → deleted users remain active.
- **No partition** → queries scan every file and retention is expensive.
- **Composite key omitted** → threat-intel revisions become duplicate rows.
- **Reset only locally** → dlt restores pipeline state from the destination.
  `run.py reset` deletes both the local state and the `raw` S3 prefix.
