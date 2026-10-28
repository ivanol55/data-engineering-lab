# Data Engineering Lab

A local, offline-first data engineering course. You build the parts of a real
pipeline that can be wrong in ways that still look plausible: keys, write
dispositions, cursors, grain, windows, joins, delivery guarantees, PII, and
point-in-time training sets. The repo provides the plumbing that fails loudly.

The scenario is a login risk service. A fictional company must decide, for every
login, whether to allow it, require MFA, or block it. Data comes from an
application Postgres database, a deterministic event generator that injects
attacks, and a daily threat-intel list. By module 7 a FastAPI service makes the
decision in real time; by module 9 a trained model replaces the hand-written
rules.

```
generator ──► Kafka ──► Flink ──► Valkey ──► FastAPI
    │            │        │                     │
    │            └── CDC ─┘                     └── decision events ──► Kafka
    ▼
historical files ──► dlt ──► Iceberg (SeaweedFS) ◄── Lakekeeper ◄── Trino / DuckDB
                         ▲
Postgres app DB ─────────┘
```

`ARCHITECTURE.md` has the full diagram with modules marked.

## Prerequisites

- Linux or macOS, 8 GB of RAM available to Docker (16 GB recommended for the
  full stack).
- Docker Engine 24+ and Docker Compose v2.
- GNU Make, git, and about 12 GB of free disk for images and volumes.
- No cloud account, API key, or paid service. After the first image pull and
  image build, the lab runs offline.

Windows users can run it inside WSL2 with Docker Desktop's WSL integration.

## Quickstart

```bash
cp .env.example .env          # local-only defaults; no real secrets
make up P=core                # Postgres, SeaweedFS, Lakekeeper, Trino
make doctor                   # Docker, RAM, ports, health
make psql                     # explore the seeded application database
make check M=0                # module 0 check (fails until you fill answers.md)
```

Open:

| Service | URL | Profile |
|---|---|---|
| Trino | http://localhost:8085 | `core` |
| Lakekeeper UI | http://localhost:8181/ui/ | `core` |
| SeaweedFS S3 | http://localhost:8333 | `core` |
| Kafka (host listener) | `localhost:29092` | `stream` |
| Kafka Connect (Debezium) | http://localhost:8083 | `stream` |
| Apicurio Registry | http://localhost:8086 | `stream` |
| Kafbat UI | http://localhost:8081 | `stream` |
| Flink UI | http://localhost:8082 | `flink` |
| Dagster | http://localhost:3002 | `orchestration` |
| Grafana | http://localhost:3001 | `observability` |
| Prometheus | http://localhost:9090 | `observability` |
| FastAPI | http://localhost:8001/docs | `serving` |
| MLflow | http://localhost:5001 | `ml` |

Ports are configurable in `.env`. Defaults avoid the common `3000`, `8080`,
and `8888` collisions.

## Commands

```bash
make up P=core                     # start one or more profiles
make up P=core,tools               # tools image for ad-hoc Python
make up P=all                      # the whole stack (needs ~6-8 GB)
make build                         # build the four local images
make down                          # stop this project
make reset                         # stop and DELETE all lab volumes and state
make doctor                        # environment + health checks
make check M=1                     # behavioural checks for module 1
make check-all                     # modules that have checks (0 and 1)
make load                          # module 1: load all three sources
make load-users
make load-threat-intel
make load-events
make query Q="SELECT count(*) FROM raw.users"
make duckdb Q="SELECT count(*) FROM raw.users"
make fixtures                      # regenerate deterministic fixtures
make generator ARGS="--help"
make psql
```

`make up` is idempotent and waits for health checks. `make down` keeps volumes;
`make reset` destroys them, so the next `make up` reseeds Postgres and
recreates the lakehouse catalog. Starting `orchestration`, `serving`, or `ml`
automatically adds `core`, because those services depend on Postgres and
SeaweedFS.

## Profiles

| Profile | Services | Measured idle | Compose budget |
|---|---|---|---|
| `core` | Postgres, SeaweedFS, Lakekeeper, Trino, init jobs | ~1.0 GiB | ~4.9 GB |
| `tools` | Python image for dlt, dbt, DuckDB, checks, generator | idle (<1 MiB) | 2 GB |
| `stream` | Kafka (KRaft), Kafka Connect/Debezium, Apicurio, Kafbat | ~1.5 GiB | ~3.9 GB |
| `flink` | Flink JobManager + TaskManager | ~0.5 GiB | ~3.6 GB |
| `orchestration` | Dagster webserver + daemon | ~0.4 GiB | ~1.8 GB |
| `serving` | Valkey + FastAPI (+ `core`) | ~1.1 GiB | ~5.9 GB |
| `observability` | Prometheus + Grafana | ~0.4 GiB | ~1.3 GB |
| `ml` | MLflow | ~1.7 GiB | 2 GB |

Measured with `docker stats --no-stream` after startup and no active jobs. The
whole stack idles at roughly 5.5 GiB. Compose memory limits are set per service
so a single module cannot take the machine down; details are in `DECISIONS.md`.

## Module map

| Module | Topic | Services | Status |
|---|---|---|---|
| 0 | Environment and architecture | `core` | complete |
| 1 | Batch ingestion into the lakehouse | `core`, `tools` | complete |
| 2 | dbt modelling | `core`, `tools` | scaffold (README only) |
| 3 | Orchestration with Dagster | `core`, `orchestration` | scaffold (README only) |
| 4 | Kafka and schemas | `stream` | scaffold (README only) |
| 5 | CDC with Debezium | `stream`, `core` | scaffold (README only) |
| 6 | Flink stream processing | `stream`, `flink`, `serving` | scaffold (README only) |
| 7 | Decision service | `serving`, `stream` | scaffold (README only) |
| 8 | Consistency and governance | `core`, `stream`, `observability` | scaffold (README only) |
| 9 | Modelling | `ml`, `core` | scaffold (README only) |

Each module has `README.md`, `hints.md`, `drills.md`, `stretch.md`, and an
`exercises/` directory. Modules 2-9 currently contain no exercises or checks;
their services start, but the module work is not implemented.

## How learner gaps work

Every gap is marked in code:

```python
# TODO(learner): choose the primary key for the users table
# Why it matters: a non-unique key makes an upsert update several rows or none.
# Check: make check M=1
```

The surrounding code must still run. A placeholder may produce wrong numbers;
it must not crash. The checks test data behaviour, not source text:

- run a load twice and compare row counts;
- change one row in Postgres and reload it;
- delete a user and apply the policy declared in the learner's config;
- verify that the second users load reads only changed rows;
- inject duplicate threat-intel rows and verify the table has one row per IP.

Run `make check M=<n>` from a clean `make reset && make up P=core`. Checks
reset the tables they own before each run. On `main` every learner check fails;
on the `solutions` branch every check passes. That is the acceptance test for
the course itself.

`hints.md` gives progressive hints per gap. Each hint is inside a `<details>`
block so you can take one nudge at a time. `drills.md` contains break-it
exercises with no answer key; `stretch.md` contains open-ended extensions.

## Using AI

See the "Using AI on this module" section at the end of each module README.
The rule is consistent: use AI to explain concepts, review a decision you have
already made, or debug a loud failure. Write keys, grains, cursors, windows,
join semantics, and PII policies yourself first. Those are the parts where a
plausible wrong answer is the failure mode this course is about.

## Licence

MIT. The pinned tools have their own licences; see `DECISIONS.md`.
