# Module 1 hints

Try the change first; these are the reference answers.

<details>
<summary>Users are duplicated after a re-run</summary>

`USERS_PRIMARY_KEY` must be the natural key, and the write disposition must be
a merge. In `pipelines/ingestion/config.py`:

```python
USERS_PRIMARY_KEY = "user_id"
USERS_WRITE_DISPOSITION = "merge"
```

The source still yields a full snapshot. dlt uses the key to upsert. Do not add
an incremental cursor here: users can change without their `updated_at` moving
in a way a cursor would catch, and a full 2,000-row snapshot is cheap.

</details>

<details>
<summary>The changed user is still stale</summary>

If you only set the primary key but left `append`, both the old and new rows
exist and the check sees two matches. Set the disposition to `merge`.

</details>

<details>
<summary>Deleted users still look active</summary>

Choose a policy and implement the branch in `sources.py`:

```python
DELETION_POLICY = "soft_delete"   # or "hard_delete"
```

Soft delete keeps the row and sets `is_deleted` from `deleted_at`. Hard delete
filters the row out and uses `replace` (the code already switches to `replace`
for that policy). `"TODO"` forces `is_deleted = False` for everyone.

</details>

<details>
<summary>The event count keeps growing</summary>

Turn on the cursor:

```python
EVENTS_INCREMENTAL = True
```

The resource passes `dlt.sources.incremental("event_time")`. dlt stores the
last cursor value in pipeline state. The state lives both under
`state/dlt/` and in the destination, so a manual table drop without
`run.py reset` can resurrect old state.

</details>

<details>
<summary>The partition spec is empty</summary>

Import the helper and set the day transform:

```python
EVENTS_PARTITION = iceberg_partition.day("event_time")
```

`sources.py` only applies `iceberg_adapter` when this is not `None`. The column
must be a timestamp; `event_time` is `timestamptz` in the contract.

</details>

<details>
<summary>Threat intel has duplicate keys</summary>

Use both columns and merge:

```python
THREAT_INTEL_PRIMARY_KEY = ["indicator", "valid_from"]
THREAT_INTEL_WRITE_DISPOSITION = "merge"
```

The source deduplicates within a load package only when the key is set. That is
required because pyiceberg refuses an upsert whose source contains duplicate
keys.

</details>

<details>
<summary>`make check M=1` resets my data</summary>

That is intentional. Each scenario calls `run.py reset`, which drops the three
`raw` tables, deletes the `raw` prefix in SeaweedFS, and clears dlt state. It
does not touch Postgres or the fixtures.

</details>
