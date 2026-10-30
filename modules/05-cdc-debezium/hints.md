# Module 5 — CDC with Debezium — hints

These are progressive hints, one per hard decision. Open one at a time.
The values live in `cdc/config.py`.

<details>
<summary>Hint 1: Enable logical replication first</summary>

Postgres needs `wal_level=logical` and enough `max_wal_senders`. The setting is not reloadable; restart the service. Check with `SHOW wal_level` before debugging the connector.

The compose file already starts Postgres with the right settings. Run
`docker compose --profile tools run --rm tools python cdc/run.py reset` before
`setup` so the slot and connector offsets start clean.

</details>

<details>
<summary>Hint 2: A tombstone is not a row</summary>

After a delete, Debezium emits the delete event and then a record with a null value. If your sink deserialises nulls as an empty row, you will create a ghost user. Decide whether to keep or drop the tombstone, and make the consumer agree.

Set `EMIT_TOMBSTONES = True` and `APPLY_DELETES = True`. The consumer ignores
the null tombstone and applies the `op=d` event.

</details>

<details>
<summary>Hint 3: Watch the slot</summary>

`pg_replication_slots` shows the confirmed flush position. An inactive slot retains WAL forever. Delete the slot only after you have stopped the connector, or you will lose the change stream.

`cdc/run.py reset` stops the connector, deletes its offsets, waits for the
slot to become idle, then drops it.

</details>
