# Module 5 — CDC with Debezium

**Time:** 3–4 hours. **Profile:** `stream` + `core`.

## Goal

Stop taking a full snapshot of `users` every night. Stream the changes, and
then deal with the consequences: initial snapshots, deletes, tombstones, schema
changes, and the difference between "the row changed" and "the row is now
gone".

By the end you should have:

- logical replication enabled on the application Postgres;
- a Debezium connector capturing `public.users` and `public.roles`;
- an initial snapshot followed by incremental changes;
- a consumer that applies inserts, updates, and deletes to a target table;
- a documented answer to what happens when a column is added or dropped.

## What already exists

- Postgres 18.6 with the application schema and 2,000 seeded users.
- Debezium Connect 3.7.0.Final on <http://localhost:8083>.
- Kafka 4.4.0 and Apicurio Registry from module 4.
- Postgres starts with `wal_level=logical`, `max_wal_senders=10` and
  `max_replication_slots=10`, so the connector can create its slot.
- `cdc/run.py` has `reset`, `setup` and `consume` commands. The sink tables
  are `cdc_users` and `cdc_roles` in the application database.
- `make reset` destroys the volume, so you can start from a clean snapshot.

## What the CDC pipeline does

1. Configure Postgres for logical replication (`wal_level=logical`, a
   replication slot, and enough `max_wal_senders`). Restart the service.
2. Register a Debezium connector with `plugin.name=pgoutput`, a table include
   list, and a topic prefix.
3. Watch the initial snapshot. Compare its row count with `SELECT count(*)`.
4. Insert, update, and delete a user. Follow the change through Kafka and
   apply it to a target table.
5. Decide how to handle the tombstone record after a delete. A tombstone is
   not a row with nulls; it is a compaction marker.
6. Add a column to `users` and observe the schema change event. Decide whether
   the consumer can tolerate it.

## Your task

Edit `cdc/config.py`, then run:

```bash
python cdc/run.py reset
python cdc/run.py setup
python cdc/run.py consume
make check M=5
```

| Setting | Wrong value | What it breaks |
|---|---|---|
| `SNAPSHOT_MODE` | `no_data` | the target starts empty |
| `INCLUDE_TABLES` | `public.users` | role changes never reach the sink |
| `EMIT_TOMBSTONES` | `False` | a consumer cannot tell delete from empty |
| `SINK_UPSERT` | `False` | updates are ignored |
| `APPLY_DELETES` | `False` | deleted users stay active |

## Decisions to make yourself

| Decision | Why it is easy to get wrong |
|---|---|
| Snapshot mode | `initial` only runs once; a new connector on an existing slot may skip it |
| Delete handling | Dropping tombstones loses the delete signal; keeping them requires a consumer that understands them |
| Primary key | Debezium uses the table PK; a key change looks like a delete plus an insert |
| Topic naming | A topic prefix change starts a new history and breaks consumers |
| Schema changes | Adding a nullable column is easy; dropping or renaming one is not |
| Replication slot lag | An inactive slot retains WAL until the disk fills |

## Useful commands

```bash
curl -s http://localhost:8083/connectors
curl -s http://localhost:8083/connectors/<name>/status
docker compose --profile stream exec kafka \
  /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 --topic <prefix>.public.users --from-beginning
```

## Done when

- The connector is `RUNNING` and its task is `RUNNING`.
- The initial snapshot matches the source row count.
- An insert, an update, and a delete each appear in the topic and are applied
  to the target exactly once.
- A schema change is either handled or fails loudly; it is not silently
  dropped.
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
