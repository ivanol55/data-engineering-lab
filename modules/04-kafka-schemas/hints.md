# Module 4 — Kafka and schemas — hints

These are progressive hints, one per hard decision. Open one at a time.
The values live in `streaming/config.py`.

<details>
<summary>Hint 1: Choose the key from the consumer</summary>

Ask what needs ordering or co-location. Per-user state wants `user_id` as the key. Per-event consumers do not care. A null key is a decision, not a default.

Set `MESSAGE_KEY = "user_id"` and `PARTITION_COUNT = 3`.

</details>

<details>
<summary>Hint 2: Commit after the sink</summary>

The safe order is read, process, write the sink, then commit the offset. That gives at-least-once. If the sink is not idempotent, a crash between write and commit duplicates data.

Set `AUTO_COMMIT = False` and `SINK_IDEMPOTENT = True`.

</details>

<details>
<summary>Hint 3: Test compatibility before renaming</summary>

Register a schema that renames a field and watch the registry reject it under `BACKWARD`. Then add an optional field with a default and watch it pass. Write down which change each mode allows.

Set `SCHEMA_COMPATIBILITY = "BACKWARD"`. Renaming a required field is
rejected; adding an optional field with a default is accepted.

</details>
