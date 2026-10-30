# Module 0 — The lab and its contracts

**Time:** 60–90 minutes. **Profile:** `core`.

## What you are building towards

The lab models one security question:

> Given a login attempt, should it be allowed, challenged with MFA, or blocked?

The application database (`Postgres`) is the system of record for identity. A
deterministic generator produces login events, including a controlled mix of
attacks. A daily threat-intel fixture lists suspicious indicators. Later modules
land all three sources in an open table format, stream events, transform them,
serve decisions, and score risk.

You do not need any cloud account. Every component is local, open source, and
runs in Docker Compose. After the first image pull and tools-image build, the
lab runs offline.

## Before you start

You do not need to know these words yet. This is the minimum needed for module
0; the full list is in [`docs/GLOSSARY.md`](../../docs/GLOSSARY.md).

| Word | Plain meaning | In this lab |
|---|---|---|
| **System of record** | The authoritative copy of a fact | Postgres owns users and roles |
| **OLTP** | A database built for small, frequent reads and writes | Postgres handles sign-ups, updates, deletes |
| **OLAP** | A system built for large scans and aggregations | Trino and DuckDB answer analytical queries |
| **Object storage** | A service that stores files by key | SeaweedFS stores Parquet files under `s3://lakehouse/` |
| **Table format** | Metadata that turns a folder of files into a table | Iceberg adds schemas, snapshots, and partitions |
| **Catalog** | The address book for tables | Lakekeeper maps `iceberg.raw.users` to Iceberg metadata |
| **Batch** | Processing a group of data on a schedule | Module 1 loads seven daily files |
| **Stream** | Processing events as they arrive | Modules 4–6 use Kafka and Flink |

The mental model is a library:

- **SeaweedFS** is the building full of shelves (files).
- **Iceberg** is the catalogue card that says which books belong to which
  collection and which edition is current.
- **Lakekeeper** is the librarian who knows where the catalogue cards are.
- **Trino** is the reading room where you ask questions.

A folder of Parquet files is not a table. The table format is what makes the
files queryable, versioned, and safe to update.

## The core profile

```
                   ┌──────────────────────────────┐
  host :8085 ─────▶│ Trino                        │
                   │  ├── postgresql catalog ─────┼──▶ Postgres :5432
                   │  └── iceberg catalog ────────┼──▶ Lakekeeper :8181
                   └──────────────────────────────┘         │
                                                            ▼
                   ┌──────────────────────────────┐   ┌──────────────┐
  host :8333 ─────▶│ SeaweedFS S3                 │◀──│ warehouse    │
                   └──────────────────────────────┘   │ metadata +   │
                                                      │ Parquet      │
                   ┌──────────────────────────────┐   └──────────────┘
  make ... ───────▶│ tools (dlt, pyiceberg, dbt,  │
                   │ duckdb, pytest, generator)   │
                   └──────────────────────────────┘
```

| Component | Role | Why this one |
|---|---|---|
| Postgres 18 | Application database and metadata stores | Boring, transactional, already familiar |
| SeaweedFS | S3-compatible object storage | Small all-in-one binary, Apache-2.0, no MinIO |
| Lakekeeper | Iceberg REST catalog | Open source, multi-arch, simple local bootstrap |
| Trino | SQL engine | Reads Postgres and Iceberg with one dialect |
| `tools` | Python image | Pinned dlt, pyiceberg, DuckDB, dbt, pytest |

`make doctor` checks the host side: Docker, Compose, free RAM, port conflicts,
container health, and the core endpoints. It cannot prove that a pipeline is
correct; that is what the module checks are for.

## Guided walkthrough

Follow the steps in order. Each step tells you what to run, what you should see,
and what it proves.

### Step 1 — Start the core profile

```bash
cp .env.example .env     # only if .env does not exist
make up P=core
make doctor
```

**You should see:** containers for Postgres, SeaweedFS, Lakekeeper, Trino, and
the one-shot init jobs become healthy. `make doctor` ends with
`all checks passed`.

**What this proves:** the plumbing is up. A healthy container is not a correct
pipeline; it only means the process is running.

### Step 2 — Look at the application data

```bash
make psql
```

Then run:

```sql
SELECT account_status, count(*) FROM users GROUP BY 1 ORDER BY 1;
SELECT count(*) FROM users WHERE deleted_at IS NOT NULL;
SELECT role_id, count(*) FROM users GROUP BY 1 ORDER BY 1;
```

**You should see:** 2,000 users, 5 roles, and 42 rows with a non-null
`deleted_at`. The statuses are `active`, `disabled`, `locked`, and `suspended`.

**What this proves:** Postgres is the system of record, and it already contains
the messy cases the later modules must handle: disabled accounts, soft deletes,
and role assignments.

Exit `psql` with `\q`.

### Step 3 — Query Postgres through Trino

```bash
make query Q='SELECT count(*) FROM postgresql.public.users'
make query Q='SHOW SCHEMAS IN iceberg'
```

**You should see:** `2000` from the first query, and a `raw` schema from the
second.

**What this proves:** Trino can read two different systems with one SQL
dialect. The Postgres catalog is a live view; the Iceberg catalog is a table
format managed by Lakekeeper.

### Step 4 — Generate and inspect the fixtures

```bash
make fixtures
make generator ARGS="plan --days 2"
```

**You should see:** seven JSONL files under `fixtures/events/`, and a plan that
shows the daily event and attack counts.

**What this proves:** the input data is deterministic. The same seed and start
date produce the same event ids on every machine, which makes the checks
repeatable.

### Step 5 — Read the architecture

Open `ARCHITECTURE.md` and `DECISIONS.md`. You do not need to memorise them.
Look for:

- which component owns which kind of state;
- why the lab uses SeaweedFS instead of MinIO;
- why Lakekeeper advertises `http://lakekeeper:8181` instead of `localhost`.

### Step 6 — Write the model in your own words

Open `modules/00-environment/answers.md`. Each question has:

- **What this question is really asking** — the idea behind it;
- **What to cover** — the points a good answer includes;
- **A sentence starter** — a way to begin if the blank page is intimidating.

Replace the `TODO(learner)` line with a short answer. You do not need an essay;
three or four sentences that use the key terms are enough. If you are stuck,
open the matching hint in `hints.md`.

### Step 7 — Run the check

```bash
make check M=0
```

**You should see:** seven passing tests once the answers are filled in.

**What this proves:** the environment is healthy, the fixtures are
deterministic, and you can explain the system you are about to build on.

## Check yourself

These are not graded. Try to answer before opening the hint.

<details>
<summary>Why not query Postgres directly from every dashboard?</summary>

Because analytical scans compete with application traffic, and because the
dashboard would need to understand the application schema. A lakehouse copy
isolates the load and gives you a stable, queryable history. The trade-off is
freshness: the copy is only as new as the last load.

</details>

<details>
<summary>What is the difference between SeaweedFS and Lakekeeper?</summary>

SeaweedFS stores bytes (Parquet files, metadata files). Lakekeeper stores the
address book: which table exists, which metadata file is current, and what
schema it has. You can lose the catalog and still have the files, but you
cannot query them as tables until the catalog is rebuilt.

</details>

<details>
<summary>Why does the lab use a deterministic generator?</summary>

So a check can say “there are 14,000 events and 8% are attacks” and mean it on
every machine. Random data would make failures hard to reproduce and would turn
every exercise into a debugging session about the fixture instead of the
pipeline.

</details>

## Done when

- `make up P=core` and `make doctor` pass.
- Postgres has 2,000 users, 5 roles, and 42 soft-deleted users.
- Trino can read both `postgresql.public.users` and the `iceberg.raw` namespace.
- `answers.md` has no `TODO(learner)` left and `make check M=0` passes.

## Notes

- The tools image is built locally (`de-lab-tools:local`). The first build needs
  PyPI; later runs use the cached image. This is the one documented exception to
  “pull-only” startup.
- Host ports are configurable in `.env`. Defaults: Postgres `5432`, SeaweedFS
  `8333`, Lakekeeper `8181`, Trino `8085`.
- Do not put real credentials in `.env`. Everything in this repo is local-only.
