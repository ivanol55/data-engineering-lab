# Module 2 — dbt modelling — hints

These are progressive hints, one per hard decision. Open one at a time. The
values live in `modules/02-dbt-modelling/exercises/config.py`.

<details>
<summary>Hint 1: Start with the grain</summary>

Write the grain as one sentence before any SQL: "one row per <thing> per <time>". If you cannot name the thing and the time, the model is not ready. Then check `count(*)` vs `count(distinct key)` on the source and on the model.

Set `FCT_INCREMENTAL_STRATEGY = "merge"` and keep
`FCT_UNIQUE_KEY = "event_id"`. With `append`, the second build duplicates
every event.

</details>

<details>
<summary>Hint 2: Find the fan-out</summary>

Before and after the intel join, run `count(*)` grouped by `event_id`. Any event with more than one row means the join matched several revisions. Constrain on `valid_from <= event_time < valid_to` and deduplicate the intel side first.

Set `INTEL_JOIN_MODE = "latest_valid"`. The model then keeps one revision
inside its validity window instead of fanning out.

</details>

<details>
<summary>Hint 3: Prove idempotence</summary>

Run `dbt build` twice from the same raw tables and compare row counts. Then delete one user in Postgres, reload module 1, and run dbt again. The fact table should not change; the dimension should.

Set `FCT_LATE_WINDOW_DAYS = 2`. Zero means the incremental cursor drops an
event that arrives a few hours late.

</details>
