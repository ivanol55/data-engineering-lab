# Module 5 exercises

The connector, sink and decisions live in `cdc/`.

1. Start core and stream:

   ```bash
   make up P=core,stream
   ```

2. Reset the connector, replication slot and target tables:

   ```bash
   python cdc/run.py reset
   python cdc/run.py setup
   ```

3. Consume the initial snapshot:

   ```bash
   python cdc/run.py consume
   ```

4. Compare source and target:

   ```bash
   make psql
   # select count(*) from users;
   # select count(*) from cdc_users;
   ```

5. Make a change in the source and consume it:

   ```sql
   update users set email = 'changed@acme.example', updated_at = now()
   where user_id = '00000000-0000-0000-0000-000000000001';
   ```

   Then `python cdc/run.py consume` and check `cdc_users`.

6. Delete the row. The consumer must remove it from `cdc_users` and the topic
   must contain a null-value tombstone for the key.

7. Fix the values in `cdc/config.py`:

   | Setting | Reference |
   |---|---|
   | `SNAPSHOT_MODE` | `"initial"` |
   | `INCLUDE_TABLES` | `"public.users,public.roles"` |
   | `EMIT_TOMBSTONES` | `True` |
   | `SINK_UPSERT` | `True` |
   | `APPLY_DELETES` | `True` |

8. Run `make check M=5`.

9. Add a nullable column to `users`, update a row, and consume. The sink
   ignores unknown fields, so the change must not break it. Drop the column
   afterwards.
