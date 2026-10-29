# Runbook: raw events are stale

1. Check `lab_exporter_last_success_timestamp_seconds` in Prometheus. If it is
   old, the exporter is down, not the pipeline.
2. Check the module 1 loader: `make load-events` and the `dlt` logs.
3. Query `select max(event_time) from iceberg.raw.login_events`.
4. If the fixtures are historical, confirm this is the expected lab state and
   silence the alert for the exercise.
