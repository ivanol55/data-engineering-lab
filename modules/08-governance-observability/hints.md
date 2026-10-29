# Module 8 — Consistency and governance — hints

These are progressive hints, one per hard decision. Open one at a time.
The files you own are `compose/prometheus/alerts.yml`,
`dashboards/lab-overview.json`, `governance/catalogue.yml` and
`governance/deletion.md`.

<details>
<summary>Hint 1: Freshness is max event time</summary>

`max(event_time)` compared with `now()` tells you whether the data is current. The last successful load time only tells you the job ran. Export both and alert on the first.

The exporter already publishes `lab_table_max_event_time_seconds`. Set
`RawEventsStale` to `time() - max(...) > 86400` with `for: 10m`.

</details>

<details>
<summary>Hint 2: Keep labels bounded</summary>

Never put `user_id`, `event_id`, or a raw IP in a Prometheus label. Use a rule or a histogram. Estimate the series count before you add a label.

The dashboard should query `lab_table_row_count`,
`lab_kafka_consumer_lag`, `lab_connector_failed_tasks` and
`lab_decision_latency_seconds_bucket`. Keep the labels to `table` and `group`.

</details>

<details>
<summary>Hint 3: Alerts need a duration and a runbook</summary>

A threshold without `for:` flaps on every scrape. Add a duration, a severity, and a link to the action. Test the alert by breaking the pipeline on purpose.

Reference: lag `> 1000` for `10m`, dependency error ratio `> 0.05` for `5m`,
and a `runbook_url` under `docs/runbooks/`. The catalogue and deletion
procedure are prose: make them specific to this lab's five systems.

</details>
