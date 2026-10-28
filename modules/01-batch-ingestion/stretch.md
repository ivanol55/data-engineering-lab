# Module 1 stretch

Optional, not checked.

1. **Late events.** Generate an event with `event_time` older than the current
   cursor and run `make load-events`. It is silently skipped. Design a fix:
   either a lookback window (`incremental(..., lag=...)`), a staging table with
   a dedupe step, or a merge keyed on `event_id`. Write down which one you would
   ship and why.

2. **Hard delete.** Set `DELETION_POLICY = "hard_delete"`, run
   `run.py reset` and `make load`. Confirm the deleted user is gone and the
   table still has one row per remaining user. What did you lose?

3. **Schema evolution.** Add a nullable column to the users query (for example
   `manager_id`), load, and confirm Iceberg evolved the schema without
   rewriting the old files. Then remove it. What happens to the column in
   Iceberg?

4. **Small files.** Load one day at a time (`make load-events` after removing
   the other files from a temporary fixtures directory) and inspect the number
   of Parquet files in the `login_events` metadata. How would you compact them
   without breaking readers?

5. **Threat-intel join.** The intel feed has a low-confidence decoy. Build a
   query that ranks indicators by `confidence * severity` and joins events.
   How many false positives does the decoy create?

6. **Deletion as a security control.** Suppose an employee is terminated at
   09:00 and their account is disabled in Postgres. Events keep arriving until
   09:05. Which table should the decision service consult, and how fresh must
   it be? This is the bridge to modules 3 and 7.
