# Deletion procedure

## Scope

A deletion request is identified by `user_id` and, when the requester cannot
supply it, by the verified email address. The identifier appears in five
systems:

| System | Where | Copy |
|---|---|---|
| Postgres | `users`, `roles` reference | system of record |
| Iceberg / S3 | `raw.users`, `raw.login_events`, `raw.threat_intel`, `marts.*` | historical snapshots |
| Kafka | `login.events`, `cdc.public.users`, `login.decisions` | log segments |
| Valkey | `last_country:<user_id>`, `decision:<request_id>` | feature/cache |
| MLflow | training runs, datasets and model artifacts | derived |

## Procedure

1. **Freeze.** Set `account_status = 'disabled'` and `deleted_at = now()` in
   Postgres. Confirm the decision service blocks the user.
2. **Postgres.** Hard-delete the row only after the retention window for the
   audit trail has passed; until then keep the soft-deleted row and purge the
   PII columns (`email`, `full_name`) in place.
3. **Iceberg.** Rewrite the affected partitions without the user's rows and
   expire the old snapshots:

   ```sql
   delete from iceberg.raw.login_events where user_id = :user_id;
   delete from iceberg.marts.fct_login_events where user_id = :user_id;
   delete from iceberg.marts.dim_users where user_id = :user_id;
   alter table iceberg.raw.login_events execute expire_snapshots(
     older_than => now() - interval '1' day
   );
   ```

   Confirm the S3 objects for the expired snapshots are gone before declaring
   success.
4. **Kafka.** Publish a tombstone for the user's key on `login.events` and
   `cdc.public.users`, then wait for the retention window to delete the older
   segments. A compacted topic keeps the latest value; a tombstone is the only
   way to remove it.
5. **Valkey.** Delete `last_country:<user_id>` and every `decision:*` key whose
   payload contains the user id.
6. **MLflow.** Delete the runs and artifacts that contain the user's rows.
   Record the deletion in the run description so the audit trail survives the
   data.

## Verification

- `select count(*) from users where user_id = :user_id` returns 0 or the
  PII-free tombstone row.
- Trino returns 0 for the user id in every table listed above.
- A Kafka consumer from the earliest offset sees no value with the user id
  after the retention window.
- `valkey-cli --scan --pattern '*<user_id>*'` returns nothing.
- MLflow search by the user id returns no run.

## Retention

Audit records that reference the deletion (who asked, when, which systems were
cleared) are kept for 365 days. The data itself is not kept for "just in case":
a copy that outlives the request is a breach, not a backup.
