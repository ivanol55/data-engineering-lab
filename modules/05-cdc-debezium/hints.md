# Module 5 — CDC with Debezium — hints

These are progressive hints, one per hard decision. Open one at a time.

> This module is a scaffold: the exercises and checks are not implemented
> yet. The hints describe the decisions the module will test.

<details>
<summary>Hint 1: Enable logical replication first</summary>

Postgres needs `wal_level=logical` and enough `max_wal_senders`. The setting is not reloadable; restart the service. Check with `SHOW wal_level` before debugging the connector.

</details>

<details>
<summary>Hint 2: A tombstone is not a row</summary>

After a delete, Debezium emits the delete event and then a record with a null value. If your sink deserialises nulls as an empty row, you will create a ghost user. Decide whether to keep or drop the tombstone, and make the consumer agree.

</details>

<details>
<summary>Hint 3: Watch the slot</summary>

`pg_replication_slots` shows the confirmed flush position. An inactive slot retains WAL forever. Delete the slot only after you have stopped the connector, or you will lose the change stream.

</details>
