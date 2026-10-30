# Module 2 exercises

The dbt project is written. You own the four decisions in
`modules/02-dbt-modelling/exercises/config.py`; the wrapper passes them to dbt
as `--vars`.

1. Load module 1 first:

   ```bash
   make up P=core
   make load
   ```

2. Start the tools profile and inspect the raw grain:

   ```bash
   make up P=core,tools
   make query Q='SELECT count(*) AS rows, count(DISTINCT event_id) AS events
                   FROM iceberg.raw.login_events'
   ```

3. Build once with the wrong config:

   ```bash
   docker compose --profile tools run --rm tools \
     python modules/02-dbt-modelling/exercises/run.py build
   ```

   Build a second time. With `FCT_INCREMENTAL_STRATEGY = "append"`, the fact
   table doubles.

4. Count intel matches per event:

   ```bash
   make query Q='SELECT count(*) AS rows, count(DISTINCT event_id) AS events
                   FROM iceberg.marts.fct_login_events'
   ```

   The fixture feed alone happens not to fan out: only one indicator has
   several revisions, and no event uses it. To see the bug, insert an expired
   indicator for a day-seven event, rebuild, and count the matches outside the
   validity window. The check does exactly that:

   ```bash
   make query Q="
   INSERT INTO threat_intel (
     indicator, indicator_type, threat_type, confidence, severity, source,
     description, valid_from, valid_to, updated_at, generator_version,
     _dlt_load_id, _dlt_id
   )
   SELECT source_ip, 'ip', 'expired_test', 99, 'critical', 'manual',
          'expired indicator used by the exercise',
          DATE '2026-09-01', DATE '2026-09-02',
          TIMESTAMP '2026-09-02 06:00:00 UTC', 'manual', 'manual',
          'manual-expired'
   FROM login_events
   WHERE event_time >= TIMESTAMP '2026-09-07 00:00:00 UTC'
     AND source_ip NOT IN (SELECT indicator FROM threat_intel)
   LIMIT 1
   "
   ```

   With `INTEL_JOIN_MODE = "indicator_only"`, this returns a positive count:

   ```bash
   make query Q='SELECT count(*) FROM iceberg.marts.fct_login_events
                  WHERE intel_hit AND CAST(event_time AS date) > intel_valid_to'
   ```

   With `"latest_valid"` it returns 0, because the join respects
   `valid_from` / `valid_to`.

5. Fix the values:

   | Setting | Reference |
   |---|---|
   | `FCT_INCREMENTAL_STRATEGY` | `"merge"` |
   | `FCT_UNIQUE_KEY` | `"event_id"` |
   | `INTEL_JOIN_MODE` | `"latest_valid"` |
   | `FCT_LATE_WINDOW_DAYS` | `2` |

6. Rebuild with `--full-refresh` once to clear the duplicated rows, then run a
   normal build twice and compare row counts:

   ```bash
   docker compose --profile tools run --rm tools \
     python modules/02-dbt-modelling/exercises/run.py build --full-refresh
   docker compose --profile tools run --rm tools \
     python modules/02-dbt-modelling/exercises/run.py build
   ```

7. Run the dbt tests:

   ```bash
   docker compose --profile tools run --rm tools \
     python modules/02-dbt-modelling/exercises/run.py test
   ```

8. Run the check:

   ```bash
   make check M=2
   ```

9. Drill: insert a synthetic event dated inside the late window, rebuild
   incrementally, and confirm it appears. Then set
   `FCT_LATE_WINDOW_DAYS = 0` and confirm it is dropped.
