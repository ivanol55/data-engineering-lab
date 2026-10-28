# Architecture

## One scenario, three source shapes

The lab answers a single question: **should this login be allowed, challenged
with MFA, or blocked?** Everything else exists to make that question hard in the
ways real data engineering is hard.

```
                         ┌─────────────────────────────────────────────┐
                         │              application data               │
                         │  Postgres: users, roles, status, deleted_at │
                         └───────────────┬─────────────────────────────┘
                                         │ snapshot / CDC
                                         ▼
  deterministic generator ──────► ┌──────────────┐
  (attacks + noise, JSONL/Kafka)  │  ingestion   │
  daily threat-intel fixture ────►│  dlt / Kafka │
                                  └──────┬───────┘
                                         ▼
                         ┌──────────────────────────────────┐
                         │ Iceberg tables on SeaweedFS      │
                         │  raw.users                       │
                         │  raw.login_events  (day partition)│
                         │  raw.threat_intel                │
                         │  staging / marts (later modules) │
                         └───────────────┬──────────────────┘
                                         │
              ┌──────────────────────────┼──────────────────────────┐
              ▼                          ▼                          ▼
        Trino / DuckDB              dbt models                 Flink / API
        ad-hoc SQL                  transformations            decisions
```

Later modules add Kafka and Flink for the live path, Dagster for scheduling,
dbt for modelling, Prometheus/Grafana for freshness and lag, a FastAPI decision
service backed by Valkey, and MLflow for the risk model. None of those change
the batch contracts established in module 1.

## Components

| Component | Version | Responsibility | State |
|---|---|---|---|
| Postgres | 18.6 | Application DB; Lakekeeper, Dagster and MLflow metadata DBs | `pgdata` volume |
| SeaweedFS | 4.51 | S3-compatible object storage for Iceberg data and artifacts | `seaweedfs` volume |
| Lakekeeper | 0.14.2 | Iceberg REST catalog (warehouse, namespaces, table metadata) | Postgres `lakekeeper` DB |
| Trino | 484 | SQL over Postgres and Iceberg | stateless |
| tools | Python 3.12 | dlt, pyiceberg, DuckDB, dbt, pytest, generator | repo bind mount |
| Kafka | 4.4.0 | Event log for the live path | `kafka` volume (later) |
| Flink | 2.3.0 | Stateful stream processing | checkpoint dir (later) |
| Dagster | 1.13.27 | Asset orchestration and schedules | Postgres `dagster` DB |
| Valkey | 9.0.7 | Low-latency decision cache | append-only volume |
| FastAPI | local | Decision API | stateless |
| Prometheus / Grafana | 3.15.1 / 13.2.5 | Metrics and dashboards | volumes |
| MLflow | 3.17.2 | Experiment tracking and model registry | Postgres + S3 |

All images are pinned. Licences and multi-arch checks are in `DECISIONS.md`.

## Storage layout

The Lakekeeper warehouse is rooted at `s3://lakehouse/warehouse`. dlt writes
each dataset below it:

```
s3://lakehouse/warehouse/
  raw/
    users/{data,metadata}/
    login_events/{data,metadata}/
    threat_intel/{data,metadata}/
    _dlt_loads/  _dlt_pipeline_state/  _dlt_version/
  staging/        # dbt (module 2)
  marts/          # dbt (module 2)
  mlflow/         # artifacts (module 9)
```

Iceberg metadata is the source of truth for table contents. Parquet files
without the catalog are just files. `make reset` deletes both the catalog
entries and the `raw` prefix; otherwise dlt can restore pipeline state from the
destination and resurrect old assumptions.

## Networks and ports

Everything runs on the Compose network `de-lab_lab`. Host ports are in `.env`:

| Service | Host port | Internal |
|---|---|---|
| Postgres | 5432 | 5432 |
| SeaweedFS S3 | 8333 | 8333 |
| SeaweedFS master | 9333 | 9333 |
| Lakekeeper | 8181 | 8181 |
| Trino | 8085 | 8080 |
| Kafka external listener | 29092 | 9092 |
| Debezium Connect | 8083 | 8083 |
| Apicurio | 8086 | 8080 |
| Kafbat | 8081 | 8080 |
| Flink UI | 8082 | 8081 |
| Dagster | 3002 | 3000 |
| Valkey | 6379 | 6379 |
| FastAPI | 8001 | 8000 |
| Prometheus | 9090 | 9090 |
| Grafana | 3001 | 3000 |
| MLflow | 5001 | 5000 |

`localhost` inside a container is not the host and not another service. Clients
always use service names (`postgres`, `lakekeeper`, `seaweedfs`, `trino`). This
is why Lakekeeper advertises `http://lakekeeper:8181` as its base URI.

## Profiles and memory budget

Profiles exist so a module only pays for what it uses. Each service has a
Compose `mem_limit`; the sum per profile is the budget. Measured idle values are
in `DECISIONS.md`.

| Profile | Services | Budget |
|---|---|---|
| `core` | Postgres, SeaweedFS, Lakekeeper, Trino, init | ~4.9 GB |
| `tools` | Python tooling | 2 GB |
| `stream` | Kafka, Apicurio, Kafbat, Debezium | ~3.8 GB |
| `flink` | JobManager + TaskManager | ~3.5 GB |
| `orchestration` | Dagster webserver + daemon | ~1.8 GB |
| `serving` | Valkey + API (+ `core`) | ~5.9 GB |
| `observability` | Prometheus + Grafana | ~1.3 GB |
| `ml` | MLflow | 2 GB |

`make up P=core,stream` composes profiles. `make up P=all` starts everything.
Measured idle is about 6 GiB; the limits above are ceilings, not reservations.
Starting `orchestration`, `serving`, or `ml` automatically includes `core`,
because all three depend on Postgres and SeaweedFS.

## Failure model

The course distinguishes two kinds of failure:

1. **Loud plumbing failures.** A missing bucket, unreachable catalog, failed
   migration, bad SQL, or failed check exits non-zero with a message. The
   bootstrap script is idempotent but never swallows an unexpected HTTP error.
2. **Silent learner failures.** A wrong key, disposition, cursor, deletion
   policy, or partition runs to completion and produces a plausible table. The
   checks catch it by changing data and running the pipeline twice.

`TODO(learner)` marks the second kind. The check suite is the executable
specification: on `main` the learner checks fail; on `solutions` they pass.

## Determinism and safety

- Event ids are UUIDv5 of `(seed, UTC date, per-day sequence)`. Regenerating a
  single day produces the same ids as the original backfill.
- The default seed (`1337`) and start date (`2026-09-01`) are fixed, so fixtures
  are byte-identical across machines.
- Source IPs come only from RFC 5737 documentation ranges (`192.0.2.0/24`,
  `198.51.100.0/24`, `203.0.113.0/24`). No generated traffic can reach a real
  host.
- Credentials in `.env` are local-only and intentionally weak. There is no
  authentication on Lakekeeper, Trino, Kafka, or the API. Do not expose these
  ports to an untrusted network.

## Non-goals

- Production HA, TLS, SSO, or secret management.
- Multi-tenant isolation.
- A real threat-intelligence feed. The daily fixture is synthetic and includes
  a deliberate low-confidence decoy.
- Exactly-once end-to-end guarantees. Module 4/6 explain where the boundaries
  actually are.
