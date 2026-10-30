# Module 8 — Observability and governance

**Time:** 3–4 hours. **Profile:** `core` + `stream` + `serving` +
`observability`.

## What you are building towards

A pipeline that runs is not a pipeline you can operate. This module answers two
questions:

1. **Is the data correct right now?** Freshness, row counts, lag, failed
   connector tasks, decision latency.
2. **Who is allowed to keep it?** Ownership, retention, PII, and a deletion
   procedure that reaches every copy.

By the end you should have:

- freshness and row-count metrics for the raw tables and the marts;
- Kafka consumer lag and failed connector-task metrics;
- decision latency and decision-count metrics from the API;
- four alerts with a threshold, a duration, a severity, and a runbook link;
- a dashboard that shows the data, not just `up`;
- a table catalogue with owner, grain, retention, PII, and upstream;
- a deletion procedure that reaches Postgres, Iceberg, Kafka, Valkey, and
  MLflow.

## Before you start

| Word | Plain meaning | In this module |
|---|---|---|
| **Metric** | A number sampled over time | `lab_table_row_count` |
| **Gauge** | A value that goes up and down | Row count, lag |
| **Counter** | A value that only increases | Decisions, dependency errors |
| **Scrape** | Prometheus reading a target's metrics | Every 15 seconds |
| **Freshness** | How old the newest data is | `time() - max(event_time)` |
| **Alert rule** | A query plus a duration, severity, and action | `RawEventsStale` |
| **Runbook** | The steps an on-call person follows | `docs/runbooks/*.md` |
| **Cardinality** | The number of distinct label combinations | A `user_id` label explodes it |
| **Catalogue** | The inventory of tables and their owners | `governance/catalogue.yml` |
| **PII** | Personally identifiable information | Email, name, IP, device id |
| **Retention** | How long data is kept before deletion | `retention_days` |
| **Deletion procedure** | The ordered steps that remove a person's data | `governance/deletion.md` |

The mental model is a hospital:

- A **metric** is a vital-signs monitor. It is useful only if someone reads it.
- An **alert** is the monitor's alarm: it needs a threshold, a delay so a
  single bad sample does not wake everyone, and a note saying what to do.
- The **catalogue** is the patient chart: who owns this table, what one row
  means, how long it is kept, and which columns are sensitive.
- The **deletion procedure** is the discharge checklist. Removing the name from
  the front desk is not enough if the lab, the pharmacy, and the archive still
  have a copy.

`up` is the least interesting metric in the lab. A container can be healthy
while its table has not changed in two days.

## Guided walkthrough

### Step 1 — Start the observability profile

```bash
make up P=core,stream,serving,observability
```

Open:

- Prometheus: <http://localhost:9090>
- Grafana: <http://localhost:3001> (anonymous read; admin password `labadmin`)
- API metrics: <http://localhost:8001/metrics>

### Step 2 — Confirm the scrape targets

In Prometheus, open **Status → Targets**.

**You should see** `prometheus`, `api`, and `exporter` all `UP`.

**What this proves:** Prometheus can reach the three targets. It does not prove
the metrics are useful; a target can be up and expose only `up`.

### Step 3 — Query the metrics by hand

In the Prometheus query box, run:

```promql
lab_table_row_count
lab_table_max_event_time_seconds
lab_kafka_consumer_lag
lab_connector_failed_tasks
lab_exporter_last_success_timestamp_seconds
```

**You should see:** one series per table, group, or connector. If a table has
never been loaded, it has no series; that is normal before module 1.

Freshness is a subtraction, not a stored value:

```promql
time() - max by (table) (lab_table_max_event_time_seconds)
```

**You should see** a number of seconds per table. A large number means the
newest event is old.

### Step 4 — Read the placeholder alerts

Open `compose/prometheus/alerts.yml`. The four rules exist, but their
thresholds can never fire in practice:

- `RawEventsStale` uses `315360000` seconds, which is ten years.
- `KafkaConsumerLagHigh` uses `99999999`, which is effectively "never".
- `DecisionDependencyErrors` fires only above a 99% error rate.
- `ConnectorTaskFailed` is missing.

A rule that can never fire is worse than no rule: it looks like monitoring.

### Step 5 — Fix the four alerts

Set the following values. Each rule also needs `for:`, a `severity` label, and
a `runbook_url` annotation.

| Alert | Expression | `for` | Severity |
|---|---|---|---|
| `RawEventsStale` | `time() - max(...) > 86400` | `10m` | warning |
| `KafkaConsumerLagHigh` | `sum by (group) (lab_kafka_consumer_lag) > 1000` | `10m` | warning |
| `DecisionDependencyErrors` | error ratio `> 0.05` | `5m` | critical |
| `ConnectorTaskFailed` | `lab_connector_failed_tasks > 0` | `5m` | critical |

The error-ratio expression is:

```promql
(
  sum(rate(lab_dependency_errors_total[5m]))
  /
  clamp_min(sum(rate(lab_decisions_total[5m])), 0.001)
) > 0.05
```

Use the runbooks in `docs/runbooks/`:

- `stale-events.md`
- `kafka-lag.md`
- `decision-errors.md`
- `connector-failed.md`

Reload the rules:

```bash
docker compose --profile observability restart prometheus
```

Then open **Status → Rules** in Prometheus.

**You should see:** all four alerts loaded.

**Why these numbers:** one day of event time is the product's freshness
expectation. A thousand unread records sustained for ten minutes is a consumer
that is not keeping up, not a momentary batch. A 5% dependency error rate is an
incident; 99% is an outage you notice by hand.

### Step 6 — Add dashboard panels

Open `dashboards/lab-overview.json`. It has two `sum(up)` panels. Add at least
five panels that query:

- `lab_table_max_event_time_seconds`
- `lab_table_row_count`
- `lab_kafka_consumer_lag`
- `lab_decision_latency_seconds_bucket`
- `lab_connector_failed_tasks`

A minimal panel looks like this:

```json
{
  "type": "timeseries",
  "title": "Table freshness",
  "datasource": {"type": "prometheus", "uid": "prometheus"},
  "targets": [
    {
      "expr": "time() - max by (table) (lab_table_max_event_time_seconds)",
      "legendFormat": "{{table}}",
      "refId": "A"
    }
  ],
  "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0}
}
```

For p95 latency, use:

```promql
histogram_quantile(
  0.95,
  sum by (le) (rate(lab_decision_latency_seconds_bucket[5m]))
)
```

The `solutions` branch has a complete reference dashboard; compare with it
after you have written your own panels.

### Step 7 — Fill the catalogue

Open `governance/catalogue.yml`. The check expects these five tables:
`raw.users`, `raw.login_events`, `raw.threat_intel`, `marts.fct_login_events`,
`marts.dim_users`.

For each one, fill:

```yaml
raw.login_events:
  owner: security-analytics
  grain: one row per login event
  retention_days: 90
  pii_columns: [email, source_ip, device_id]
  upstream: [generator.login_events]
```

The reference values are:

| Table | Owner | Grain | Retention | PII | Upstream |
|---|---|---|---|---|---|
| `raw.users` | identity-platform | one row per user, current snapshot | 365 | email, full_name | postgres.public.users |
| `raw.login_events` | security-analytics | one row per login event | 90 | email, source_ip, device_id | generator.login_events |
| `raw.threat_intel` | security-analytics | one row per indicator revision | 365 | none | generator.threat_intel |
| `marts.fct_login_events` | security-analytics | one row per event, enriched | 90 | email, source_ip, device_id | raw.users, raw.login_events, raw.threat_intel |
| `marts.dim_users` | identity-platform | one row per user, current values | 365 | email, full_name | raw.users |

**Why a team and not a person:** a person changes jobs; a team has a rota. An
unowned table has nobody to page.

**Why retention differs:** the fact table is large and the product needs 90
days; the user dimension is small and the audit needs a year. Retention is a
product and legal decision, not a storage default.

### Step 8 — Write the deletion procedure

Open `governance/deletion.md`. It needs four sections and must mention all five
systems:

- `## Scope`: the identifier (`user_id`, verified email) and the five systems.
- `## Procedure`: ordered steps for Postgres, Iceberg/S3, Kafka, Valkey, MLflow.
- `## Verification`: how you prove no copy remains.
- `## Retention`: what is kept for audit, and for how long.

The key idea: a soft delete in Postgres is not a deletion. The lakehouse has
snapshots, Kafka has log segments, Valkey has cache keys, and MLflow has
training runs. The procedure must reach each one and then verify.

### Step 9 — Run the check

```bash
make check M=8
```

**You should see:** eight passing tests. The check restarts Prometheus so the
new rules load, queries the live targets, reads your dashboard JSON, parses the
catalogue, and scans the deletion procedure for every system.

## The choice, explained

| Decision | Reference | Why |
|---|---|---|
| Freshness | max event time, not load time | A load can succeed with no new data |
| Stale threshold | 24 hours | The product's freshness expectation |
| Lag threshold | 1,000 for 10 minutes | A sustained lag is an incident; one sample is noise |
| Error threshold | 5% for 5 minutes | Small enough to catch a real dependency problem |
| Alert duration | non-empty `for:` | A single bad sample must not page |
| Runbook | one per alert | An alert without an action is noise |
| Dashboard | data metrics, not just `up` | A green `up` panel hides stale data |
| Catalogue | owner, grain, retention, PII, upstream | An unowned table has nobody to page |
| Deletion | all five systems plus verification | A copy that survives the request is a breach |

**Cardinality.** Do not put `user_id` in a metric label. Each distinct value
creates a time series, and a few thousand users turn a small metric into a
memory problem. Use `table`, `group`, `connector`, or `decision` as labels.

**Freshness is not "the job ran".** The job can run every night and load an
empty file. `time() - max(event_time)` measures the data, not the scheduler.

## Check yourself

<details>
<summary>Why is a `for:` duration part of a good alert?</summary>

Because metrics are noisy. A single scrape above the threshold is not an
incident; a sustained condition is. The duration filters flakes and gives the
on-call person a signal worth acting on.

</details>

<details>
<summary>What is metric cardinality, and why does it matter?</summary>

It is the number of distinct label combinations, which is the number of time
series Prometheus stores. A `user_id` label creates one series per user. High
cardinality costs memory and slows queries, and it is easy to add by accident.

</details>

<details>
<summary>Why does the catalogue need a grain, not just an owner?</summary>

Because the owner needs to know what one row means to judge a change. "One row
per event" tells you that a duplicate is a bug; "one row per event per
indicator" tells you the join is allowed to fan out.

</details>

<details>
<summary>Why is deleting a row from Postgres not a deletion request?</summary>

Because copies exist elsewhere: Iceberg snapshots, Kafka segments, Valkey
cache entries, and MLflow training data. Each has its own retention clock. A
deletion procedure must reach all of them and verify that none remains.

</details>

<details>
<summary>What is the difference between a gauge and a counter?</summary>

A gauge goes up and down, such as row count or lag. A counter only increases,
such as decisions or errors. You query them differently: a counter is usually
wrapped in `rate()`, a gauge is read directly.

</details>

## Useful commands

```bash
make up P=core,stream,serving,observability
open http://localhost:9090/targets
open http://localhost:3001
docker compose --profile observability restart prometheus
```

## Done when

- Prometheus scrapes `prometheus`, `api`, and `exporter`, all `UP`.
- The exporter completes a cycle and the API metrics reach Prometheus.
- The four alerts load with a bounded threshold, a duration, and a runbook.
- The dashboard queries freshness, row counts, lag, connector health, and
  decision latency.
- The catalogue covers every table with an owner and a retention period.
- The deletion procedure covers Postgres, Iceberg, Kafka, Valkey, and MLflow.
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
