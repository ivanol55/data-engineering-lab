# Runbook: connector task failed

1. Open <http://localhost:8083/connectors/users-cdc/status>.
2. Read the task trace. A stale replication slot or a changed Postgres
   publication is the usual cause.
3. Run `python cdc/run.py reset` and `python cdc/run.py setup` to recreate the
   slot and connector offsets.
4. Replay the snapshot and confirm `cdc_users` matches `users`.
