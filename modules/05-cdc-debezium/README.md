# Module 5 — CDC with Debezium

**Time:** 3–4 hours. **Profile:** `stream` + `core`.

## What you are building towards

Module 1 copies the whole `users` table every night. That is simple, but it
re-reads 2,000 rows to find two changes, and it cannot tell you *when* a user
was deleted. This module reads the database's write-ahead log instead, so every
insert, update, and delete becomes an event.

By the end you should have:

- logical replication enabled on the application Postgres;
- a Debezium connector capturing `public.users` and `public.roles`;
- an initial snapshot followed by incremental changes;
- a consumer that applies inserts, updates, and deletes to a target table;
- a documented answer to what happens when a column is added or dropped.

## Before you start

| Word | Plain meaning | In this module |
|---|---|---|
| **CDC** | Change data capture: turn each database change into an event | Debezium reads the WAL |
| **WAL** | Write-ahead log: Postgres writes every change before the table | The source of the events |
| **Logical replication** | Postgres decodes the WAL into rows | `wal_level=logical` |
| **Replication slot** | A bookmark that keeps WAL until a consumer reads it | `de_lab_cdc` |
| **Publication** | The set of tables exposed for replication | `de_lab_cdc_pub` |
| **Snapshot** | The initial copy of existing rows before streaming | 2,000 users |
| **Debezium** | The connector that reads Postgres and writes Kafka | `users-cdc` |
| **Tombstone** | A Kafka record with a null value, meaning "delete this key" | Emitted after a delete |
| **Upsert** | Insert if new, update if the key exists | The sink's write mode |
| **Schema history** | Kafka topic where Debezium stores the source schema | `cdc.schema-history` |

The mental model is a court reporter:

- The **WAL** is the stenographer's tape. Every change is written there before
  it changes the table.
- A **replication slot** is a bookmark in the tape. If nobody reads, the tape
  grows until the disk fills.
- A **snapshot** is the transcript of everything that happened before the
  reporter arrived.
- A **tombstone** is the note "this person is gone", not a page with every
  field blank.

Debezium emits a record for the insert, a record for the update, and a record
with `op = "d"` plus a null-value tombstone for the delete. The sink must
understand all three.

## Guided walkthrough

### Step 1 — Start the profiles

```bash
make up P=core,stream
```

### Step 2 — Register the connector with the wrong config

```bash
docker compose --profile tools run --rm tools python cdc/run.py reset
docker compose --profile tools run --rm tools python cdc/run.py setup
docker compose --profile tools run --rm tools python cdc/run.py consume
docker compose exec -T postgres psql -U app -d app -tAc \
  "select count(*) from cdc_users"
```

**You should see:**

```
deleted connector, slot, publication, target tables and topics
connector users-cdc: RUNNING
{'upsert': 0, 'delete': 0, 'tombstone': 0, 'ignored': 0}
0
```

**What this proves:** the connector is healthy and the target is empty.
`SNAPSHOT_MODE = "no_data"` registered the connector but never copied the
existing 2,000 users. A `RUNNING` connector is not a working pipeline.

### Step 3 — Look at the replication slot and publication

```bash
make psql
```

Then:

```sql
SELECT slot_name, active FROM pg_replication_slots;
SELECT * FROM pg_publication_tables;
```

**You should see:** the `de_lab_cdc` slot and only `public.users` in the
publication. `INCLUDE_TABLES` omits `public.roles`.

Exit with `\q`.

### Step 4 — Fix the five values

Open `cdc/config.py` and set:

| Setting | Wrong | Reference |
|---|---|---|
| `SNAPSHOT_MODE` | `"no_data"` | `"initial"` |
| `INCLUDE_TABLES` | `"public.users"` | `"public.users,public.roles"` |
| `EMIT_TOMBSTONES` | `False` | `True` |
| `SINK_UPSERT` | `False` | `True` |
| `APPLY_DELETES` | `False` | `True` |

Reset and snapshot again:

```bash
docker compose --profile tools run --rm tools python cdc/run.py reset
docker compose --profile tools run --rm tools python cdc/run.py setup
docker compose --profile tools run --rm tools python cdc/run.py consume
docker compose exec -T postgres psql -U app -d app -tAc \
  "select (select count(*) from cdc_users), (select count(*) from cdc_roles)"
```

**You should see:** `{'upsert': 2005, ...}` and `2000|5`. The snapshot copied
2,000 users and 5 roles.

### Step 5 — Insert, update, and delete

In one `psql` session, insert a test user, update the email, then delete the
row. After each change, run the consumer:

```bash
docker compose --profile tools run --rm tools python cdc/run.py consume
```

**You should see:** `upsert` counts for the insert and the update, and a
`delete` count for the delete. Query `cdc_users` after the delete; the test
user must be gone.

The tombstone is a separate record with a null value. The check reads the topic
and asserts at least one tombstone exists.

### Step 6 — Run the check

```bash
make check M=5
```

**You should see:** four passing tests. The check registers the connector,
compares the snapshot with the source, applies an insert, an update, and a
delete, and looks for a tombstone in the topic.

## The choice, explained

| Setting | What it controls | Why the reference is right |
|---|---|---|
| `SNAPSHOT_MODE = "initial"` | Whether existing rows are copied | Without it the target starts empty and never catches up |
| `INCLUDE_TABLES = "public.users,public.roles"` | Which tables the connector captures | Role renames matter to the consumer |
| `EMIT_TOMBSTONES = True` | Whether a delete emits a null-value record | A consumer cannot tell delete from an empty record otherwise |
| `SINK_UPSERT = True` | Whether the sink updates an existing key | An update must replace the row, not be ignored |
| `APPLY_DELETES = True` | Whether the sink deletes on `op = "d"` | Deleted users must not stay active |

**Why `initial` and not `no_data`.** `no_data` is for a source that is already
empty or for a connector that will only stream future changes. This source has
2,000 existing users, so the target needs a snapshot. `initial` takes it once;
later changes stream from the slot.

**Why both tables.** `roles` is small and changes rarely, which is exactly why
a rename is easy to miss. If the consumer joins users to roles, an old role
name becomes wrong for every user. Include the table and pay the tiny cost.

**Why tombstones.** Debezium's delete event has `before` and `after = null`.
The tombstone is a separate record with a null value, used by compacted topics
to remove the key. A consumer that drops tombstones can still apply the delete
event, but a compacted topic has no other way to forget the key. Keep the
contract intact.

**Why upsert and apply deletes.** Debezium is at-least-once: a retry can deliver
the same change twice. An `INSERT ... ON CONFLICT DO NOTHING` makes the second
delivery a no-op, so an update is silently lost. An upsert replaces the row,
and a delete removes it. The pair makes a replay safe and an update visible.

**Why the reset is careful.** Deleting the connector does not delete its
offsets. If you recreate it without stopping it and deleting the offsets, it
resumes at an LSN the new slot does not have. `reset` also waits for the slot to
become idle before dropping it, because Postgres refuses to drop an active
slot.

## Check yourself

<details>
<summary>What happens to WAL if a replication slot is never read?</summary>

Postgres keeps the WAL the slot still needs. An inactive slot retains it until
the disk fills. Monitoring slot lag is part of operating CDC; deleting a
connector must also remove its slot.

</details>

<details>
<summary>Why is a tombstone not a row full of nulls?</summary>

A row with null columns is still a row with a key. A tombstone is a record with
a null *value*, which a compacted topic interprets as "delete this key". The
distinction matters to the sink and to compaction.

</details>

<details>
<summary>Why does an `INSERT ... ON CONFLICT DO NOTHING` sink lose updates?</summary>

Because the row already exists. The second delivery conflicts, the statement
does nothing, and the new email or status is never written. An upsert updates
the non-key columns on conflict.

</details>

<details>
<summary>What is the difference between the snapshot and the stream?</summary>

The snapshot copies the rows that existed before the connector started. The
stream carries changes after the slot's start position. A correct pipeline needs
both, and the handover must not lose or duplicate rows.

</details>

<details>
<summary>Why include `roles` if users already carry `role_id`?</summary>

Because `role_id` is a number, and a consumer that wants the role name needs the
role table. If a role is renamed, a users-only pipeline keeps the old meaning.
Including the small table keeps the join correct.

</details>

## Useful commands

```bash
curl -s http://localhost:8083/connectors
curl -s http://localhost:8083/connectors/users-cdc/status
docker compose --profile stream exec kafka \
  /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 --topic cdc.public.users --from-beginning
```

## Done when

- The connector is `RUNNING` and its task is `RUNNING`.
- The initial snapshot matches the source row count (2,000 users, 5 roles).
- An insert, an update, and a delete each appear in the topic and are applied
  to the target exactly once.
- A tombstone exists for the delete.
- `make check M=5` fails on `main`, passes on `solutions`.

## Failure modes to watch

- **Snapshot rerun on a live slot.** The connector re-snapshots and the target
  gets a second copy of every row.
- **Tombstone ignored.** Deleted users stay active in the target.
- **At-least-once applied blindly.** A retry inserts a duplicate because the
  sink uses `INSERT` instead of an upsert on the PK.
- **Slot leak.** A deleted connector leaves a slot behind and Postgres WAL grows
  without bound.
- **Schema drift.** A new `NOT NULL` column breaks the sink at 3 a.m.

## Using AI on this module

Ask AI to explain Debezium's snapshot phases or the tombstone contract. Write
the apply logic and the delete policy yourself; that is where the silent bugs
live.
