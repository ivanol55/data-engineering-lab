# Module 8 — Consistency and governance

**Time:** 3–4 hours. **Profile:** `core` + `stream` + `observability`. **Status:** scaffold.

> Prometheus and Grafana start with the `observability` profile. The dashboard
> has one panel and no lab targets; metrics, alerts, lineage, and checks are
> not written yet.

## Goal

Answer "is the pipeline correct right now?" without opening a shell. Then
answer the questions that are not metrics: who owns this table, how long do we
keep it, and what happens when someone asks us to delete a person's data?

By the end you should have:

- freshness metrics for each raw table and each mart;
- Kafka consumer lag and failed-load counters;
- decision latency and block-rate metrics from the API;
- alerts with thresholds and a runbook link, not just dashboards;
- a table ownership and retention policy;
- a PII inventory and a deletion procedure that reaches Iceberg, Kafka, and
  the model store.

## What already exists

- Prometheus 3.15.1 and Grafana 13.2.5, provisioned from
  `compose/prometheus/prometheus.yml` and `compose/grafana/provisioning/`.
- One starter dashboard at `dashboards/lab-overview.json`.
- The API, Kafka, Connect, Trino, and the batch tables from earlier modules.
- Grafana is anonymous-read by default; the admin password is `labadmin`.

## What you will build

1. Choose signals. At minimum: max event time per table, row count per load,
   consumer lag, failed connector tasks, decision p95, and block rate.
2. Export them. Trino does not expose a Prometheus endpoint by default; decide
   whether to add an exporter, push from the pipeline, or query on a schedule.
3. Add Prometheus scrape targets and labels that identify the module and the
   environment.
4. Write three alerts with thresholds you can defend: stale raw events, lag
   above N for M minutes, and decision error rate.
5. Add a table catalogue: owner, grain, retention, PII columns, and upstream
   dependencies.
6. Write the deletion procedure. Deleting a user from Postgres is not enough;
   events, intel matches, features, and model training rows may all contain the
   identifier.

## Decisions to make yourself

| Decision | Why it is easy to get wrong |
|---|---|
| Freshness definition | "Last load time" is not "max event time"; a load can succeed with no new data |
| Metric cardinality | A `user_id` label explodes the time series and the Prometheus memory |
| Alert thresholds | A threshold with no duration flaps; one with too much duration misses incidents |
| Ownership | A table with no owner has no one to page |
| Retention | Iceberg snapshots and Kafka retention are separate clocks |
| PII deletion | A soft delete in Postgres leaves copies in S3, Kafka, and MLflow |

## Useful commands

```bash
make up P=observability
open http://localhost:9090/targets
open http://localhost:3001
```

## Done when

- Prometheus has at least three lab targets and all are `UP`.
- Grafana shows freshness, lag, and decision latency from real data.
- Each alert fires in a controlled test and links to a runbook.
- The catalogue lists every table with an owner and a retention period.
- The deletion procedure is exercised on a test user and leaves no copies in
  the paths you listed.
- `make check M=8` exists and fails on `main`, passes on `solutions`.

## Failure modes to watch

- **Green dashboard, stale data.** The job is up, the table has not changed in
  two days, and no panel shows it.
- **Cardinality bomb.** Per-user labels make Prometheus the largest consumer of
  RAM in the lab.
- **Alert without action.** A page that everyone ignores is worse than no page.
- **Retention mismatch.** Iceberg keeps history for 30 days, Kafka for 7, and
  the audit requirement is 90.
- **PII leak.** A "deleted" user still appears in the feature table and the
  training set.

## Using AI on this module

Ask AI to critique a metric definition or an alert threshold. Do the PII
inventory and the deletion procedure yourself; they depend on your data model
and cannot be delegated safely.
