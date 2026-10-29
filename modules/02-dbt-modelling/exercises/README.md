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

   With `INTEL_JOIN_MODE = "indicator_only"`, `rows > events`: revised
   indicators fan out.

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
