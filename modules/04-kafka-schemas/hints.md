# Module 4 — Kafka and schemas — hints

These are progressive hints, one per hard decision. Open one at a time.

> This module is a scaffold: the exercises and checks are not implemented
> yet. The hints describe the decisions the module will test.

<details>
<summary>Hint 1: Choose the key from the consumer</summary>

Ask what needs ordering or co-location. Per-user state wants `user_id` as the key. Per-event consumers do not care. A null key is a decision, not a default.

</details>

<details>
<summary>Hint 2: Commit after the sink</summary>

The safe order is read, process, write the sink, then commit the offset. That gives at-least-once. If the sink is not idempotent, a crash between write and commit duplicates data.

</details>

<details>
<summary>Hint 3: Test compatibility before renaming</summary>

Register a schema that renames a field and watch the registry reject it under `BACKWARD`. Then add an optional field with a default and watch it pass. Write down which change each mode allows.

</details>
