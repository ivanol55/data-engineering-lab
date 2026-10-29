# Module 3 exercises

The graph lives in `orchestration/definitions.py`. The decisions you own live
in `orchestration/config.py`. Do not edit the definitions until the config
values pass; after that, extend the graph with the stretch goals.

1. Start the profile:

   ```bash
   make up P=orchestration
   ```

2. Open <http://localhost:3002> and materialise `fixture_inventory`. Confirm
   the run is stored in Postgres and survives a webserver restart.

3. Fix the four values in `orchestration/config.py`:

   | Setting | Reference |
   |---|---|
   | `PARTITION_TIMEZONE` | `UTC` |
   | `RETRY_MAX_ATTEMPTS` | `2` |
   | `EVENT_PARTITION_MODE` | `event_date` |
   | `ENABLE_ASSET_CHECKS` | `True` |

4. Run the check:

   ```bash
   make check M=3
   ```

5. In the UI, launch a backfill for `2026-09-03` only. Then query Trino:

   ```bash
   make query Q="select cast(event_time as date) as d, count(*) from login_events group by 1 order by 1"
   ```

   A correct backfill leaves one day in the table.

6. Break it on purpose: set `EVENT_PARTITION_MODE = "run_date"`, backfill a
   historical partition, and explain why the row count changed.
