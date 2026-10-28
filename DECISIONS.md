# Decisions

This file records the choices that are easy to get wrong later, including the
ones that are deliberately local-only. Versions were checked on 2026-10-28.

## Open-source substitutions

| Need | Chosen | Rejected | Why |
|---|---|---|---|
| Object storage | **SeaweedFS 4.51** (Apache-2.0) | MinIO, Garage | No MinIO in the brief. SeaweedFS is a single all-in-one server, multi-arch, and Lakekeeper documents vended-credential tests against it. Garage is also viable but needs a more involved layout/cluster config. |
| Iceberg catalog | **Lakekeeper 0.14.2** (Apache-2.0) | Nessie, Hive Metastore, JDBC catalog | REST catalog, simple bootstrap, Postgres metadata, multi-arch, no Java/Hive stack. |
| Event log | **Apache Kafka 4.4.0** (Apache-2.0) | Redpanda | Explicit brief requirement: Kafka, not Redpanda. KRaft mode avoids ZooKeeper. |
| Batch loader | **dlt 1.31.0** (Apache-2.0) | Custom Python loader, Airbyte | Small dependency, native Iceberg support via filesystem destination + pyiceberg, schema/state management built in. |
| SQL engine | **Trino 484** (Apache-2.0) | DuckDB only, Spark | Reads Postgres and Iceberg with one SQL dialect; DuckDB is kept as a second reader. |
| Table format | **Apache Iceberg** | Delta Lake, Hudi | Open, engine-neutral, good REST catalog story. |
| Stream processor | **Apache Flink 2.3.0** (Apache-2.0) | Kafka Streams, Spark Structured Streaming | Module 6 needs event time, watermarks, and state. |
| Orchestrator | **Dagster 1.13.x** (Apache-2.0) | Airflow | Asset-oriented model fits the course; lighter local footprint. |
| Cache | **Valkey 9.0.7** (BSD-3-Clause) | Redis | Open-source fork, drop-in protocol. |
| Dashboards | **Grafana 13.2.5** (AGPL-3.0) + **Prometheus 3.15.1** (Apache-2.0) | Cloud monitoring | Local, no account. Grafana is AGPL, which is open source but worth noting for redistribution. |
| ML tracking | **MLflow 3.17.2** (Apache-2.0) | Weights & Biases, cloud MLflow | Local tracking + registry, S3 artifacts. |

No cloud account, API key, or paid service is required.

## Pinned images

| Image | Tag | Licence | Multi-arch |
|---|---|---|---|
| `postgres` | `18.6` | PostgreSQL | amd64, arm64 |
| `chrislusf/seaweedfs` | `4.51` | Apache-2.0 | amd64, arm64 |
| `quay.io/lakekeeper/catalog` | `v0.14.2` | Apache-2.0 | amd64, arm64 |
| `trinodb/trino` | `484` | Apache-2.0 | amd64, arm64 |
| `apache/kafka` | `4.4.0` | Apache-2.0 | amd64, arm64 |
| `quay.io/apicurio/apicurio-registry` | `3.3.3` | Apache-2.0 | amd64, arm64 |
| `quay.io/debezium/connect` | `3.7.0.Final` | Apache-2.0 | amd64, arm64 |
| `flink` | `2.3.0` | Apache-2.0 | amd64, arm64 |
| `valkey/valkey` | `9.0.7` | BSD-3-Clause | amd64, arm64 |
| `prom/prometheus` | `v3.15.1` | Apache-2.0 | amd64, arm64 |
| `grafana/grafana` | `13.2.5` | AGPL-3.0 | amd64, arm64 |
| `ghcr.io/kafbat/kafka-ui` | `v1.3.0` | Apache-2.0 | amd64, arm64 |
| `ghcr.io/mlflow/mlflow` | `v3.17.2` | Apache-2.0 | amd64, arm64 |

The MLflow tag is the upstream reference. The lab builds
`de-lab-mlflow:local` from the same version so boto3/botocore stay on the
pinned versions above and the image does not drift from the tools image.

The lab builds four images locally:

| Image | Base | Contents |
|---|---|---|
| `de-lab-tools:local` | `python:3.12.16-slim-bookworm` | dlt, pyiceberg, DuckDB, dbt, pytest, generator |
| `de-lab-orchestration:local` | `de-lab-tools:local` | Dagster 1.13.27 + webserver + Postgres storage |
| `de-lab-api:local` | `python:3.12.16-slim-bookworm` | FastAPI, uvicorn, redis, psycopg |
| `de-lab-mlflow:local` | `python:3.12.16-slim-bookworm` | MLflow 3.17.2, boto3, psycopg |

Dagster does not publish a maintained 1.13 image, so it is built on top of the
tools image and inherits the same pins. `dagster-postgres 0.29.27` pulled
SQLAlchemy 2.1.6, which closed its Postgres connections on the first request
(`psycopg.OperationalError: the connection is closed`). The image pins
`sqlalchemy==2.0.55`, the last 2.0 line, and the webserver works.

Python pins live in `images/tools/requirements.txt`:
dlt 1.31.0, pyiceberg 0.12.0, pyarrow 26.0.0, s3fs 2026.9.0, duckdb 2.0.0,
dbt-core 1.12.6, dbt-trino 1.11.0, psycopg 3.3.6, pytest 9.2.0, and
`boto3`/`botocore` 1.43.117. Python base image: `python:3.12.16-slim-bookworm`.

### boto3 / botocore / aiobotocore

`s3fs 2026.9.0` pulls `aiobotocore 3.10`, which caps `botocore < 1.43.118`.
`boto3 1.43.120` requires `botocore >= 1.43.120`. The first tools build failed
with `ResolutionImpossible`. The fix is to hold boto3 and botocore one patch
behind (1.43.117) and move them together when s3fs/aiobotocore move.

## Local-only choices

### Ports

Defaults avoid services already common on a developer machine:

| Service | Port | Note |
|---|---|---|
| Trino | 8085 | 8080 is often taken |
| Kafka external | 29092 | 9092 stays internal |
| Grafana | 3001 | 3000 is often taken |
| Dagster | 3002 | 3000 is often taken |
| FastAPI | 8001 | 8000 is often taken |
| MLflow | 5001 | 5000 is often taken |
| SeaweedFS filer | 8888 | not published; 8888 is often taken |

Postgres (5432), Lakekeeper (8181), SeaweedFS S3 (8333), Kafka Connect (8083),
Apicurio (8086), Kafbat (8081), Flink (8082), Prometheus (9090), Valkey (6379)
keep their usual ports. All are configurable in `.env`; `make doctor` reports
conflicts.

### Postgres 18 volume path

The official Postgres 18 image sets `PGDATA=/var/lib/postgresql/18/docker`.
Mounting a volume at `/var/lib/postgresql/data` leaves the cluster outside the
volume. This repo mounts `pgdata` at `/var/lib/postgresql`.

### Trino 484 configuration

Trino 484 uses `fs.s3.enabled=true` and `s3.aws-access-key`/`s3.aws-secret-key`.
Older guides use `fs.native-s3.enabled` and different key names; those fail on
this version. The Postgres catalog is `compose/trino/catalog/postgresql.properties`.

### Lakekeeper remote signing is off

The first version enabled `remote-signing-enabled: true` in the warehouse. Reads
through Lakekeeper's S3 signing proxy intermittently returned `403 Forbidden`
against SeaweedFS, especially during pyiceberg merges. The lab now uses static
credentials (`remote-signing-enabled: false`) for the warehouse, Trino, dlt, and
DuckDB. This is simpler and reliable locally; it is not a recommendation for
production credential vending.

### Lakekeeper base URI

`LAKEKEEPER__BASE_URI` is `http://lakekeeper:8181`, not `localhost`. The catalog
returns its base URI to clients, and every client (Trino, dlt, pyiceberg) runs
inside the Compose network. Advertising `localhost` made the init container
connect to itself and fail.

### Tools image

`de-lab-tools:local` is built locally from `images/tools/Dockerfile`. This is the
one exception to "pull everything": the first build needs PyPI, and DuckDB
extensions (`iceberg`, `httpfs`, `avro`) are downloaded at build time into
`/opt/duckdb-extensions`. After that, `make up` and the checks run offline.
A registry-published image would remove this exception but adds a publishing
dependency the brief did not ask for.

DuckDB's Iceberg attach uses the legacy S3 settings (`s3_endpoint`,
`s3_access_key_id`, ...). The named-secret path did not pass credentials to the
Iceberg extension for `s3://` metadata reads.

## Data decisions

### Deterministic generator

- Seed default `1337`, start date default `2026-09-01`, 7 days, 2,000 events/day,
  8% attack events. All are configurable.
- Event ids are UUIDv5 of `(seed, UTC date, per-day sequence)`, so a single-day
  regeneration matches the original backfill. The first version keyed ids on a
  batch-wide sequence; that broke day-independent regeneration.
- Attack rotation and source-IP allocation are keyed on the absolute date, not
  the position in the batch, for the same reason.
- Source IPs use only RFC 5737 documentation ranges.
- Threat intel is derived from the same campaign plan, so some event IPs really
  do match indicators. One low-confidence decoy per day prevents "joined =
  malicious" thinking.
- Later daily intel files revise two earlier indicators with the same
  `(indicator, valid_from)` key. This is the module 1 upsert test.

### Deletion policy

`deleted_at` is a soft-delete timestamp. Two policies are accepted:

- `soft_delete` (reference solution): keep the row, set `is_deleted = true`.
  Preserves identity and history; consumers must filter.
- `hard_delete`: omit the row and replace the snapshot. Simpler consumers, but
  historical references break.

`TODO` is the deliberate wrong default: every deleted user stays active. That is
a security bug, not a style choice.

### Events are append + incremental

Events are immutable facts. The correct write is append, with an incremental
cursor on `event_time` so a re-run does not reload history. The cursor is not a
late-data watermark: an event whose timestamp is older than the cursor is
skipped. Module 6 replaces this with event-time windows and allowed lateness.

### Users are a full snapshot + merge

Postgres is mutable. A 2,000-row full snapshot is cheap, so the pipeline does not
use a cursor; it merges on `user_id`. An incremental cursor on `updated_at`
would be cheaper at scale but can miss changes made with a stale clock.

### Threat intel needs a composite key

The natural key is `(indicator, valid_from)`. A merge keeps the newest revision.
PyIceberg's upsert rejects duplicate keys inside one load package, so the dlt
resource deduplicates to the latest `updated_at` per key before loading. This is
source-side dedupe in addition to the target merge, not a replacement for it.

### Partitioning

`login_events` is partitioned by `day(event_time)`. This makes daily filters
prune and retention cheap. The cost is more small files if events are loaded in
tiny batches; module 2/6 discuss compaction. dlt's Iceberg writer supports
partition creation, but not partition evolution (changing the spec later).

## Checks

- `make check M=<n>` starts `core`, runs pytest inside the tools image, and
  exits non-zero on failure.
- Module 0 checks the environment and that `answers.md` has no TODO
  placeholders. Module 1 checks behaviour, not source text: it mutates Postgres,
  reruns the pipeline, adds a day of events, and inspects Iceberg.
- Each module 1 scenario resets the `raw` dataset, including the S3 prefix and
  dlt state. Local state alone is not enough: dlt restores state from the
  destination.
- On `main` the learner checks fail. On `solutions` they pass. This is the
  acceptance test for the course itself.

## Measured memory

Idle, `docker stats --no-stream`, after `make up` and no active queries. Budgets
are Compose `mem_limit`s, not reservations.

| Profile | Measured idle | Compose budget | Notes |
|---|---|---|---|
| `core` | ~1.0 GiB | ~4.9 GiB | Trino ~0.65 GiB; SeaweedFS ~0.20; Postgres ~0.13; Lakekeeper ~0.02 |
| `core` + `tools` | ~1.0 GiB | ~6.9 GiB | tools idles at <1 MiB; checks add ~0.2 GiB while running |
| `stream` | ~1.5 GiB | ~3.8 GiB | Kafka ~0.59 GiB; Connect ~0.39; Kafbat ~0.29; Apicurio ~0.23 |
| `flink` | ~0.5 GiB | ~3.5 GiB | JobManager ~0.21 GiB; TaskManager ~0.26 |
| `orchestration` | ~0.4 GiB | ~1.8 GiB | webserver ~0.22 GiB; daemon ~0.20 |
| `serving` | ~1.1 GiB | ~5.9 GiB | API ~0.05 GiB; Valkey ~0.004 idle; `core` is added automatically |
| `observability` | ~0.4 GiB | ~1.3 GiB | Grafana ~0.37 GiB; Prometheus ~0.06 |
| `ml` | ~1.7 GiB | ~2.0 GiB | MLflow imports the full tracking stack; run with `--workers 1` |

Measured with `docker stats --no-stream` after `make up P=all`, no active jobs.
The whole stack idles at roughly 5.5 GiB. "Compose budget" is the sum of
`mem_limit` for the profile's concurrent services; it is a ceiling, not a
reservation. One-shot jobs (`lakekeeper-migrate`, `lakehouse-init`) add up to
~1 GiB during startup but exit before steady state.

MLflow initially had a 1 GiB limit and four uvicorn workers; it was OOM-killed
during startup. The lab now runs one worker and a 2 GiB limit, which idles at
~1.7 GiB. That is the largest single-service footprint in the stack.

## Known limitations

- Modules 2–9 are README-only scaffolds. Their Compose profiles and pinned
  images exist, but exercises, pipelines, and checks do not.
- No authentication or TLS anywhere. This is a laptop lab; do not expose it.
- SeaweedFS runs as a single node. It is not a durability or HA reference.
- dlt's Iceberg writer does not support partition evolution.
- The event cursor does not handle late data; that is module 6's problem.
- The generator's `is_attack` label is a teaching aid. A real system would
  derive risk from behaviour and intel, not read a ground-truth column.
- The FastAPI, Dagster, and MLflow services are placeholders until their modules
  are implemented.
