# Module 1 — Batch ingestion into Iceberg

**Time:** 2–3 hours. **Profile:** `core` + `tools`.

## Goal

Land the three sources that the rest of the lab depends on into the `raw`
namespace of the lakehouse, with write semantics that survive re-runs:

| Source | Shape | Target | Correct behaviour |
|---|---|---|---|
| Postgres `users` + `roles` | 2,000-row mutable snapshot | `raw.users` | one row per user, current values, deletion policy applied |
| Generated login events | 7 daily JSONL files, 2,000 events/day | `raw.login_events` | append only new days, no duplicate `event_id`, partitioned by day |
| Daily threat intel | 7 JSONL files with revisions | `raw.threat_intel` | one row per `(indicator, valid_from)`, newest revision wins |

The pipeline is dlt → filesystem destination → Lakekeeper → SeaweedFS. Trino
and pyiceberg read the same tables.

## How the pipeline is wired

```
modules/01-batch-ingestion/exercises/run.py   CLI: all | users | events | threat-intel | reset
        │
        ▼
pipelines/ingestion/pipeline.py               dlt pipeline, Iceberg catalog, reset
pipelines/ingestion/sources.py                three resources + row contracts
pipelines/ingestion/config.py                 credentials + the learner decisions
```

`make load` runs `run.py all`. `make load-users`, `make load-events`, and
`make load-threat-intel` run one resource. `make reset` deletes the lab volumes
and state; `run.py reset` deletes only the `raw` dataset and dlt state.

## Your task

Open `pipelines/ingestion/config.py`. Six values are deliberately wrong. The
pipeline runs with them, which is the dangerous part: it produces plausible
tables that fail the checks.

| Decision | Wrong default | What to choose |
|---|---|---|
| `USERS_PRIMARY_KEY` | `None` | `"user_id"` |
| `USERS_WRITE_DISPOSITION` | `"append"` | `"merge"` |
| `DELETION_POLICY` | `"TODO"` | `"soft_delete"` or `"hard_delete"` |
| `EVENTS_INCREMENTAL` | `False` | `True` |
| `EVENTS_PARTITION` | `None` | `iceberg_partition.day("event_time")` |
| `THREAT_INTEL_PRIMARY_KEY` | `None` | `["indicator", "valid_from"]` |
| `THREAT_INTEL_WRITE_DISPOSITION` | `"append"` | `"merge"` |

Then:

```bash
make load
make check M=1
```

The checks reset the `raw` dataset between scenarios, so you can iterate
without manually dropping tables.

### What each decision means

**Primary key + merge (users).** Postgres is mutable. A full snapshot is easy
to extract, but appending it duplicates every user and freezes old statuses. A
merge on `user_id` replaces the changed row and keeps the table at 2,000 rows.

**Deletion policy (users).** `deleted_at` is set for 42 seeded users (and for
anyone you delete later). Choose one:

- `soft_delete`: keep the row, set `is_deleted = true`. Downstream filters on
  the flag. This preserves history and is the reference solution.
- `hard_delete`: omit the row and rewrite the snapshot. Simpler for consumers,
  but you lose the identity and any FK-like references to it.

`"TODO"` keeps every deleted user looking active. That is a silent security
bug: a deleted account can still receive a risk score.

**Incremental cursor (events).** The cursor is `event_time`. On each run dlt
loads only events newer than the last loaded timestamp. Without it, every run
appends all 14,000 rows again. The cursor is not a watermark for late data:
an event that arrives with an old timestamp will be skipped. Module 3 fixes
that with a proper streaming watermark; for a batch backfill, sort files by
day and accept the limitation.

**Daily partition (events).** `iceberg_partition.day("event_time")` makes
`WHERE event_time >= ...` prune files and makes retention a metadata
operation. The trade-off is more, smaller files if you load tiny batches.

**Composite key + merge (threat intel).** The feed revises earlier indicators:
the same `(indicator, valid_from)` appears again with higher confidence. An
append keeps both revisions and a join double-counts. A merge keeps the newest
payload. dlt's Iceberg upsert also rejects duplicate keys inside one load
package, so the resource keeps the latest revision per key before loading.

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
- `make check M=1` passes.

## Failure modes to watch

- **Append instead of merge** → counts double on the second run.
- **No incremental cursor** → the whole history is re-loaded.
- **No deletion handling** → deleted users remain active.
- **No partition** → queries scan every file and retention is expensive.
- **Composite key omitted** → threat-intel revisions become duplicate rows.
- **Reset only locally** → dlt restores pipeline state from the destination.
  `run.py reset` deletes both the local state and the `raw` S3 prefix.
