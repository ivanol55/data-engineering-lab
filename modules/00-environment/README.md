# Module 0 — The lab and its contracts

**Time:** 45–60 minutes. **Profile:** `core`.

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

## Exercise

1. Copy the environment and start the core profile:

   ```bash
   cp .env.example .env     # only if .env does not exist
   make up P=core
   make doctor
   ```

2. Look at the application data. Notice the identity columns, the statuses, and
   the users with `deleted_at` set:

   ```bash
   make psql
   ```

   ```sql
   SELECT account_status, count(*) FROM users GROUP BY 1 ORDER BY 1;
   SELECT count(*) FROM users WHERE deleted_at IS NOT NULL;
   SELECT role_id, count(*) FROM users GROUP BY 1 ORDER BY 1;
   ```

3. Query Postgres through Trino, then list the Iceberg namespaces:

   ```bash
   make query Q='SELECT count(*) FROM postgresql.public.users'
   make query Q='SHOW SCHEMAS IN iceberg'
   ```

4. Generate the deterministic fixtures and check they are stable:

   ```bash
   make fixtures
   make generator ARGS="plan --days 2"
   ```

5. Read `ARCHITECTURE.md` and `DECISIONS.md`. Then answer the eight questions in
   `answers.md`. Replace every `TODO(learner)` with a short, specific answer.

6. Run the checks:

   ```bash
   make check M=0
   ```

## Done when

- `make up P=core` and `make doctor` pass.
- Postgres has 2,000 users, 5 roles, and 42 soft-deleted users.
- Trino can read both `postgresql.public.users` and the `iceberg.raw` namespace.
- `answers.md` has no `TODO(learner)` left and `make check M=0` passes.

## Notes

- The tools image is built locally (`de-lab-tools:local`). The first build needs
  PyPI; later runs use the cached image. This is the one documented exception to
  "pull-only" startup.
- Host ports are configurable in `.env`. Defaults: Postgres `5432`, SeaweedFS
  `8333`, Lakekeeper `8181`, Trino `8085`.
- Do not put real credentials in `.env`. Everything in this repo is local-only.
