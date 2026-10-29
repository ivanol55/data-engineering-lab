# Module 8 exercises

The exporter and the Grafana datasource are wired. You own the alerts, the
dashboard, the catalogue and the deletion procedure.

1. Start the profiles:

   ```bash
   make up P=observability
   ```

2. Open <http://localhost:9090/targets>. Confirm `prometheus`, `api` and
   `exporter` are `UP`.

3. Query the exporter by hand:

   ```bash
   curl -s http://localhost:9101/metrics | grep '^lab_'
   ```

   `lab_table_max_event_time_seconds` is the freshness signal;
   `lab_kafka_consumer_lag` is the lag signal.

4. Fix the four alerts in `compose/prometheus/alerts.yml`:

   | Alert | Reference |
   |---|---|
   | `RawEventsStale` | `time() - max(...) > 86400`, `for: 10m` |
   | `KafkaConsumerLagHigh` | `> 1000`, `for: 10m` |
   | `DecisionDependencyErrors` | ratio `> 0.05`, `for: 5m` |
   | `ConnectorTaskFailed` | `> 0`, `for: 5m` |

   Every alert needs a `severity` and a `runbook_url`.

5. Add panels to `dashboards/lab-overview.json` for freshness, row counts,
   lag, connector health, decision p95 and block rate. Reload Grafana at
   <http://localhost:3001>.

6. Fill `governance/catalogue.yml`. The check expects `raw.users`,
   `raw.login_events`, `raw.threat_intel`, `marts.fct_login_events` and
   `marts.dim_users`, each with an owner, grain, retention, PII list and
   upstream.

7. Write `governance/deletion.md` with `## Scope`, `## Procedure`,
   `## Verification` and `## Retention`. It must mention Postgres, Iceberg,
   Kafka, Valkey and MLflow.

8. Restart Prometheus and run the check:

   ```bash
   docker compose --profile observability restart prometheus
   make check M=8
   ```

9. Drill: break one alert on purpose. Set `KafkaConsumerLagHigh` to
   `> 99999999`, restart Prometheus, and confirm the alert never leaves
   `inactive` while a consumer is visibly behind.
