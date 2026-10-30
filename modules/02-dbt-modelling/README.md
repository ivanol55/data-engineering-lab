# Module 2 — dbt modelling

**Time:** 3–4 hours. **Profile:** `core` + `tools`.

## What you are building towards

Module 1 gave you three raw tables. They are correct at the row level, but they
are not yet a model: a user and an event are in separate tables, and threat
intel is a list of indicators with validity windows. This module turns them into
tables a decision service can query without re-deriving the same rules.

| Layer | Model | Grain (what one row means) | Purpose |
|---|---|---|---|
| staging | `stg_users` | one row per `user_id` | current identity, deletion flag normalised |
| staging | `stg_login_events` | one row per `event_id` | typed events, no duplicates |
| staging | `stg_threat_intel` | one row per `(indicator, valid_from)` | latest revision only |
| intermediate | `int_login_risk_inputs` | one row per event | event + user + matching intel |
| marts | `fct_login_events` | one row per event | decision features and outcome |
| marts | `dim_users` | one row per user | current identity attributes |

The hard part is not SQL syntax. It is choosing a grain, making an incremental
model idempotent, and testing the assumptions that joins quietly break.

## Before you start

| Word | Plain meaning | In this module |
|---|---|---|
| **Fact table** | One row per thing that happened | `fct_login_events`, one row per login |
| **Dimension table** | Descriptive attributes of an entity | `dim_users`, one row per user |
| **Grain** | The meaning of one row | "One row per login event" |
| **Staging model** | A cleaned copy of one raw table | `stg_*` |
| **Mart** | A table built for a consumer | `fct_*`, `dim_*` |
| **Incremental model** | A model that adds only new or changed rows | `fct_login_events` |
| **Unique key** | The column that identifies one row in a merge | `event_id` |
| **Join fan-out** | One row matching several rows and becoming several rows | An event matching three intel revisions |
| **Validity window** | The dates during which a record is true | `valid_from` / `valid_to` |
| **SCD** | Slowly changing dimension: keeping history instead of overwriting | A user's status at login time |
| **dbt** | A tool that runs SQL models and their tests in dependency order | `dbt/` |

The mental model is an accounting ledger:

- A **fact** is one line in the ledger: "this login happened".
- A **dimension** is the customer card you look up to describe the line.
- The **grain** is what one line means. If a lookup returns three customer
  cards, you now have three lines and the ledger no longer balances.
- A **validity window** is the date range printed on the card. An old card is
  not wrong; it is wrong *for today*.

dbt runs the models in the order their `ref()` calls imply. The SQL is already
written; your decisions change how the fact table is built, not what the models
look like.

## Guided walkthrough

Do the steps in order. The first build uses the wrong values on purpose, so you
can see the failure before you fix it.

### Step 1 — Load module 1 and build once

```bash
make up P=core
make load
docker compose --profile tools run --rm tools \
  python modules/02-dbt-modelling/exercises/run.py build --full-refresh
```

**You should see:** dbt finishes with a summary such as
`Done. PASS=29 WARN=0 ERROR=0 SKIP=0`. The first build succeeds even though
the config is wrong. That is the point: a green build is not a correct model.

### Step 2 — Check the grain

```bash
make query Q='SELECT count(*) AS rows, count(DISTINCT event_id) AS events
               FROM iceberg.marts.fct_login_events'
```

**You should see:** `14000` rows and `14000` distinct events.

Then build a second time without `--full-refresh`:

```bash
docker compose --profile tools run --rm tools \
  python modules/02-dbt-modelling/exercises/run.py build
make query Q='SELECT count(*) FROM iceberg.marts.fct_login_events'
```

**You should see:** the row count becomes `14001`, and dbt reports an error on
the `unique_fct_login_events_event_id` test. With `append` and a zero-day late
window, the model re-adds the newest event, so one `event_id` now appears twice.

**What this proves:** an incremental model without a merge key is not
idempotent. The table still answers queries; it just answers them with
duplicate events.

### Step 3 — See an expired indicator match

The fixture data happens not to exercise an expired indicator, so insert one
by hand. This mirrors what the check does:

```bash
make query Q="
INSERT INTO threat_intel (
  indicator, indicator_type, threat_type, confidence, severity, source,
  description, valid_from, valid_to, updated_at, generator_version,
  _dlt_load_id, _dlt_id
)
SELECT source_ip, 'ip', 'expired_test', 99, 'critical', 'manual',
       'expired indicator used by the exercise',
       DATE '2026-09-01', DATE '2026-09-02',
       TIMESTAMP '2026-09-02 06:00:00 UTC', 'manual', 'manual', 'manual-expired'
FROM login_events
WHERE event_time >= TIMESTAMP '2026-09-07 00:00:00 UTC'
  AND source_ip NOT IN (SELECT indicator FROM threat_intel)
LIMIT 1
"
docker compose --profile tools run --rm tools \
  python modules/02-dbt-modelling/exercises/run.py build --full-refresh
make query Q='SELECT count(*) FROM iceberg.marts.fct_login_events
               WHERE intel_hit AND CAST(event_time AS date) > intel_valid_to'
```

**You should see:** a number greater than zero. An event on 2026-09-07 matched
an indicator that expired on 2026-09-02.

**What this proves:** joining on `indicator` alone treats an expired indicator
as current. The join must also constrain the event date to the indicator's
validity window.

### Step 4 — Fix the four values

Open `modules/02-dbt-modelling/exercises/config.py` and set:

| Setting | Wrong | Reference |
|---|---|---|
| `FCT_INCREMENTAL_STRATEGY` | `"append"` | `"merge"` |
| `FCT_UNIQUE_KEY` | `"event_id"` | `"event_id"` (already right) |
| `INTEL_JOIN_MODE` | `"indicator_only"` | `"latest_valid"` |
| `FCT_LATE_WINDOW_DAYS` | `0` | `2` |

The wrapper passes these to dbt as `--vars`, so you never edit the SQL to
change the strategy.

### Step 5 — Rebuild and prove it

```bash
docker compose --profile tools run --rm tools \
  python modules/02-dbt-modelling/exercises/run.py build --full-refresh
docker compose --profile tools run --rm tools \
  python modules/02-dbt-modelling/exercises/run.py build
make query Q='SELECT count(*) FROM iceberg.marts.fct_login_events'
```

**You should see:** `14000` after the full refresh and still `14000` after the
normal build. The `unique_fct_login_events_event_id` test passes.

### Step 6 — Run the check

```bash
make check M=2
```

**You should see:** five passing tests. The check resets and reloads the raw
layer, inserts its own expired indicator, and checks the grain, the validity
window, idempotency, late events, and the user-delete behaviour.

## The choice, explained

| Setting | What it controls | Why the reference is right |
|---|---|---|
| `FCT_INCREMENTAL_STRATEGY = "merge"` | How a second build writes | A merge on `event_id` replaces the same event instead of adding it |
| `FCT_UNIQUE_KEY = "event_id"` | The key the merge uses | The grain is one row per event, so the event id is the key |
| `INTEL_JOIN_MODE = "latest_valid"` | How intel is joined | It constrains the event date to the validity window and keeps the newest revision |
| `FCT_LATE_WINDOW_DAYS = 2` | How far back an incremental build looks | Late events inside two days are still picked up |

**Why `merge` and not `append`.** `append` is correct for an immutable event
stream only if something else deduplicates. This model is queried as a table
with one row per event, so the model itself must enforce that. A merge on
`event_id` does.

**Why `event_id` and not a composite key.** The grain is one row per event.
Adding `indicator` to the key would make an event with two intel matches into
two rows, which is exactly the fan-out the next decision prevents.

**Why `latest_valid`.** The feed revises indicators and can have overlapping
validity windows. Joining on `indicator` alone matches every revision and
ignores whether the event happened while the indicator was valid. The
`latest_valid` mode joins on the indicator *and* the event date, then keeps the
newest revision per event. It returns at most one intel row per event.

**Why a two-day late window.** An incremental build starts from
`max(event_time) - 2 days`, so an event that arrives after the cursor but
belongs to the last two days is still processed. The cost is reprocessing two
days on every run. A zero-day window is cheap and silently drops late data.

## Check yourself

<details>
<summary>What is the grain of `fct_login_events`, and how would you prove it?</summary>

One row per login event. Prove it by comparing `count(*)` with
`count(DISTINCT event_id)`; they must be equal. A dbt `unique` test on
`event_id` states the same invariant in the project.

</details>

<details>
<summary>Why does the intel join need both the indicator and the event date?</summary>

Because an indicator is only meaningful during its validity window. The same
indicator can be valid in September and expired in October, or revised with a
new confidence. Joining on the indicator alone treats every revision as current
and can turn one event into several rows.

</details>

<details>
<summary>What does `--full-refresh` do, and when do you need it?</summary>

It drops and rebuilds the model instead of applying the incremental logic. You
need it after changing the grain, the key, or the strategy, and after a bad
build has already written duplicate rows. A normal build would keep the old
rows and merge on top of them.

</details>

<details>
<summary>Why does deleting a user change `dim_users` but not the historical fact rows?</summary>

The dimension is the current view of the user, so it should change. A fact row
records what was true when the login happened; rewriting its
`user_is_deleted` flag would change history and make the model unreproducible.
Module 2's check asserts both behaviours.

</details>

<details>
<summary>What is a late-arriving event, and why can a cursor drop it?</summary>

An event whose timestamp is older than data already processed. An incremental
filter of `event_time >= max(event_time)` excludes it, because the maximum has
already moved past it. A lookback window widens the filter enough to catch it.

</details>

## Useful commands

```bash
make up P=core,tools
docker compose --profile tools run --rm tools \
  python modules/02-dbt-modelling/exercises/run.py build
docker compose --profile tools run --rm tools \
  python modules/02-dbt-modelling/exercises/run.py test
make query Q='SELECT count(*) FROM iceberg.marts.fct_login_events'
make duckdb Q='SELECT count(*) FROM fct_login_events'
```

`dbt build` runs models and tests; `dbt run` runs models only; `dbt test` runs
tests only. The wrapper exposes all three as `build`, `run`, and `test`.

## Done when

- `dbt build` is green from a clean `make reset && make up P=core`.
- Running it twice does not change row counts.
- Deleting a user in Postgres and rerunning changes the dimension, not the
  historical fact rows.
- The intel join returns at most one indicator per event and respects
  `valid_from` / `valid_to`.
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
not ask it to "write the models" before you can state the grain and the
incremental key yourself. A generated model that runs is not evidence that the
grain is right.
