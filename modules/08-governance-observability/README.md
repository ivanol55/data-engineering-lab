# Module 8 — Consistency and governance

**Time:** 3–4 hours. **Profile:** `core` + `stream` + `observability`.

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
- `images/exporter/` turns Iceberg table freshness, row counts, Kafka lag and
  Debezium task state into Prometheus gauges. The exporter is wired; the
  questions it answers are the module.
- `compose/prometheus/alerts.yml` has placeholder thresholds that can never
  fire. You own the thresholds, durations and runbook links.
- `dashboards/lab-overview.json` has one `sum(up)` panel. You own the panels.
- `governance/catalogue.yml` and `governance/deletion.md` are placeholders.
- The API, Kafka, Connect, Trino, and the batch tables from earlier modules.
- Grafana is anonymous-read by default; the admin password is `labadmin`.

## What you will build

1. Read the exporter. It already emits max event time, row count, consumer
   lag and failed connector tasks; you do not need to write a second one.
2. Fix the four alerts in `compose/prometheus/alerts.yml`. Each needs a
   threshold, a `for:` duration, a severity and a runbook link.
3. Add panels to `dashboards/lab-overview.json` for freshness, row counts,
   lag, connector health, decision p95 and block rate.
4. Fill `governance/catalogue.yml`: owner, grain, retention, PII columns and
   upstream dependencies for every table.
5. Write `governance/deletion.md`. Deleting a user from Postgres is not enough;
   Iceberg snapshots, Kafka segments, Valkey keys and MLflow artifacts may all
   contain the identifier.
6. Test one alert by breaking the pipeline on purpose, and record what fired.

## Your task

Start the profiles:

```bash
make up P=observability
```

Then edit these four files and run `make check M=8`:

| File | What it must contain |
|---|---|
| `compose/prometheus/alerts.yml` | four alerts with bounded thresholds, `for:`, severity and `runbook_url` |
| `dashboards/lab-overview.json` | panels for freshness, row counts, lag, connector health and decision latency |
| `governance/catalogue.yml` | every table with owner, grain, retention, PII and upstream |
| `governance/deletion.md` | scope, procedure, verification and retention across all five systems |

Reference thresholds: 24 hours of event time for `RawEventsStale`, 1,000
records for `KafkaConsumerLagHigh`, and a 5% dependency error rate for
`DecisionDependencyErrors`.

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

- Prometheus scrapes `prometheus`, `api` and `exporter`, all `UP`.
- The exporter completes a collection cycle and the API metrics reach
  Prometheus.
- The four alerts load, have bounded thresholds, a duration and a runbook.
- The dashboard queries freshness, row counts, lag, connector health and
  decision latency.
- The catalogue covers every table with an owner and a retention period.
- The deletion procedure covers Postgres, Iceberg, Kafka, Valkey and MLflow.
- `make check M=8` fails on `main`, passes on `solutions`.

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
