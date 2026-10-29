# Module 2 — dbt modelling

**Time:** 3–4 hours. **Profile:** `core` + `tools`.

## Goal

Turn the three raw tables from module 1 into models a decision service can
trust. The hard part is not SQL syntax; it is choosing a grain, making
incremental models idempotent, and testing the assumptions that joins quietly
break.

By the end you should have:

| Layer | Model | Grain | Purpose |
|---|---|---|---|
| staging | `stg_users` | one row per `user_id` | current identity, deletion flag normalised |
| staging | `stg_login_events` | one row per `event_id` | typed events, no duplicates |
| staging | `stg_threat_intel` | one row per `(indicator, valid_from)` | latest revision only |
| intermediate | `int_login_risk_inputs` | one row per event | event + user + matching intel |
| marts | `fct_login_events` | one row per event | decision features and outcome |
| marts | `dim_users` | one row per user | slowly changing identity attributes |

## What already exists

- `raw.users`, `raw.login_events`, `raw.threat_intel` in Iceberg, written by
  module 1.
- The `dbt/` project: staging, intermediate and mart models, schema tests,
  and two singular tests. The SQL is written; the four learner decisions are
  in `modules/02-dbt-modelling/exercises/config.py`.
- `modules/02-dbt-modelling/exercises/run.py` passes those decisions to dbt as
  `--vars`, so you never edit the models to change the strategy.
- Trino at `trino:8080` with the `iceberg` catalog. dbt talks to Trino through
  `dbt-trino`, already installed in the tools image.
- `make query Q=...` and `make duckdb Q=...` for checking results by hand.

## Your task

Load module 1 first, then change the four values in
`modules/02-dbt-modelling/exercises/config.py`:

| Setting | Wrong value | What it breaks |
|---|---|---|
| `FCT_INCREMENTAL_STRATEGY` | `"append"` | a second build duplicates every fact row |
| `FCT_UNIQUE_KEY` | `"event_id"` | the merge needs the grain key; this one is already right |
| `INTEL_JOIN_MODE` | `"indicator_only"` | revised indicators fan out one event into many rows |
| `FCT_LATE_WINDOW_DAYS` | `0` | an event that arrives after the cursor is dropped |

The reference values are `"merge"`, `"event_id"`, `"latest_valid"` and `2`.
Build with the wrapper, then run the check:

```bash
make up P=core,tools
docker compose --profile tools run --rm tools \
  python modules/02-dbt-modelling/exercises/run.py build
make check M=2
```

The models, tests and macros are already written. Read them while you decide:
the point is the grain, the incremental key and the intel window, not typing
SQL.

## Decisions to make yourself

| Decision | Why it is easy to get wrong |
|---|---|
| Grain of `fct_login_events` | "One row per event" is only true if the source is deduplicated and the join to intel is constrained to one row |
| Incremental strategy | `append` reloads history; `merge` needs a key that is actually unique; `delete+insert` needs a reliable partition filter |
| Late-arriving events | A cursor on `event_time` silently drops events that arrive after the watermark |
| Intel join | Joining on `indicator` alone multiplies rows when the feed revises an indicator |
| SCD2 vs overwrite | Overwriting loses the user's status at the time of the login, which is exactly the feature a risk model needs |
| Tests | A model can be syntactically valid and still have the wrong grain |

## Useful commands

```bash
make up P=core,tools
docker compose --profile tools run --rm tools \
  dbt build --project-dir dbt --profiles-dir dbt
make query Q='SELECT count(*) FROM iceberg.marts.fct_login_events'
```

## Done when

- `dbt build` is green from a clean `make reset && make up P=core`.
- Running it twice does not change row counts.
- Deleting a user in Postgres and rerunning changes the dimension, not the
  historical fact rows.
- The intel join returns at most one indicator per event and respects
  `valid_from`/`valid_to`.
- `make check M=2` fails on `main`, passes on `solutions`.

## Failure modes to watch

- **Fan-out join.** One event matches three intel revisions and becomes three
  fact rows. The row count looks plausible; the decision rate is wrong.
- **Grain drift.** A "current user" join makes historical facts change when a
  user moves country. The model is no longer reproducible.
- **Incremental without merge.** A rerun doubles the fact table.
- **Tests on the wrong column.** `unique(event_id)` passes while
  `unique(event_id, indicator)` is what the join actually produced.
- **dbt state in the repo.** `target/` and `logs/` are gitignored; credentials
  never go in `profiles.yml`.

## Using AI on this module

Ask AI to review a grain definition, a join constraint, or a failing test. Do
not ask it to "write the models" before you have written the grain and the
incremental key yourself. A generated model that runs is not evidence that the
grain is right.
