# Module 1 drills

Run these after `make load`.

1. Compare row count with distinct keys:

   ```bash
   make query Q='SELECT count(*), count(DISTINCT user_id) FROM iceberg.raw.users'
   make query Q='SELECT count(*), count(DISTINCT event_id) FROM iceberg.raw.login_events'
   ```

2. Show the partition spec:

   ```bash
   make query Q='SHOW CREATE TABLE iceberg.raw.login_events'
   ```

3. Events per UTC day:

   ```bash
   make query Q="SELECT date_trunc('day', event_time) AS day, count(*) FROM iceberg.raw.login_events GROUP BY 1 ORDER BY 1"
   ```

4. Attacks by type and outcome:

   ```bash
   make query Q='SELECT attack_type, outcome, count(*) FROM iceberg.raw.login_events WHERE is_attack GROUP BY 1,2 ORDER BY 1,2'
   ```

5. Join events to users and find attacks from users whose account is not active:

   ```bash
   make query Q="SELECT count(*) FROM iceberg.raw.login_events e JOIN iceberg.raw.users u USING (user_id) WHERE e.is_attack AND u.account_status <> 'active'"
   ```

6. Threat-intel revision check:

   ```bash
   make query Q='SELECT indicator, valid_from, count(*) FROM iceberg.raw.threat_intel GROUP BY 1,2 HAVING count(*) > 1'
   ```

   The result must be empty.

7. Match events to intel by source IP and validity window:

   ```bash
   make query Q="SELECT count(*) FROM iceberg.raw.login_events e JOIN iceberg.raw.threat_intel t ON e.source_ip = t.indicator AND CAST(e.event_time AS date) BETWEEN t.valid_from AND t.valid_to"
   ```

8. Re-run only users and prove the count stays at 2,000:

   ```bash
   make load-users
   make query Q='SELECT count(*) FROM iceberg.raw.users'
   ```

9. Re-run only events and prove the count stays put:

   ```bash
   make load-events
   make query Q='SELECT count(*) FROM iceberg.raw.login_events'
   ```

10. Read the same table with DuckDB:

    ```bash
    make duckdb Q='SELECT count(*) FROM login_events'
    ```
