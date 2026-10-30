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

## New to data engineering?

You do not need prior experience with data warehouses, Kafka, or machine
learning. Start with:

- [`docs/LEARNING_PATH.md`](docs/LEARNING_PATH.md) — how to work through the
  course, what the branches mean, and how to read a failing check;
- [`docs/GLOSSARY.md`](docs/GLOSSARY.md) — every term, in plain language, with
  the lab's example.

Each module begins with a “Before you start” section that teaches the idea
before asking you to change anything. The reference answer is shown next to
each decision; the goal is to understand why it is correct, not to guess.

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
| Kafbat UI | http://localhost:8087 | `stream` |
| Flink UI | http://localhost:8082 | `flink` |
| Dagster | http://localhost:3002 | `orchestration` |
| Grafana | http://localhost:3001 | `observability` |
| Prometheus | http://localhost:9090 | `observability` |
| FastAPI | http://localhost:8001/docs | `serving` |
| MLflow | http://localhost:5001 | `ml` |

Ports are configurable in `.env`. Defaults avoid the common `3000`, `8080`,
and `8888` collisions.

## How a module works

Every module follows the same pattern:

1. **Before you start** — the problem and the words, in plain language.
2. **Guided walkthrough** — commands with the output you should expect.
3. **The choice, explained** — the wrong default, the reference answer, and the
   reason.
4. **Check yourself** — short questions with answers you can reveal.
5. **Drills and stretch** — break it on purpose, then extend it.

The checks are the executable part of the lesson. On `main` they fail; on
`solutions` they pass.

## Commands

```bash
make up P=core                     # start one or more profiles
make up P=core,tools               # tools image for ad-hoc Python
make up P=all                      # the whole stack (needs ~6-8 GB)
make build                         # build the six local images
make down                          # stop this project
make reset                         # stop and DELETE all lab volumes and state
make doctor                        # environment + health checks
make check M=1                     # behavioural checks for module 1
make check-all                     # modules 0-9, in order
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
| 2 | dbt modelling | `core`, `tools` | complete |
| 3 | Orchestration with Dagster | `core`, `orchestration` | complete |
| 4 | Kafka and schemas | `stream` | complete |
| 5 | CDC with Debezium | `stream`, `core` | complete |
| 6 | Flink stream processing | `stream`, `flink`, `serving` | complete |
| 7 | Decision service | `serving`, `stream` | complete |
| 8 | Consistency and governance | `core`, `stream`, `observability` | complete |
| 9 | ML scoring | `ml`, `core` | complete |

Each module has `README.md`, `hints.md`, `drills.md`, `stretch.md`, an
`exercises/` directory and a pytest check under `checks/module_XX/`. Modules
0-1 are committed on both branches; modules 2-9 are implemented as learner
gaps with reference solutions on the `solutions` branch.

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
