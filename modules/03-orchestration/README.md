# Module 3 — Orchestration with Dagster

**Time:** 2–3 hours. **Profile:** `core` + `orchestration`. **Status:** scaffold.

> The Dagster webserver and daemon start from a custom image and load a
> placeholder asset. Schedules, real assets, exercises, and checks are not
> written yet.

## Goal

Replace "run the script and hope" with an asset graph that knows what is stale,
what failed, and what depends on what. The interesting questions are about
failure and time, not about YAML.

By the end you should have:

- assets for the three module 1 sources, the dbt models, and a freshness check;
- a schedule or sensor that runs the daily path once, not once per restart;
- retries with a bounded policy, and a run that fails loudly instead of
  writing a partial table;
- a backfill that is partition-aware and does not re-read the world.

## What already exists

- `orchestration/definitions.py` defines one asset, `fixture_inventory`, which
  counts the generated fixtures. It proves the code location and the
  Postgres-backed instance storage work.
- `orchestration/dagster.yaml` stores runs in the `dagster` Postgres database
  and disables telemetry, so the lab stays offline.
- `orchestration/workspace.yaml` loads the definitions from the image.
- `make up P=core,orchestration` builds the image and starts the webserver on
  <http://localhost:3002> and the daemon.
- The repo is mounted read-only at `/workspace`; fixtures are visible there.
  The image is rebuilt on `make up`, so edit `orchestration/definitions.py` and
  restart the profile.

## What you will build

1. Assets that call the module 1 pipeline (`run.py users|events|threat-intel`)
   and materialise the module 2 dbt models. Use `deps`, not sleeps.
2. A daily partition keyed on the event date. Decide what a backfill of one
   partition means for the incremental cursor.
3. A schedule with a timezone. Explain why "midnight local" is a bug for a
   pipeline whose cursor is UTC.
4. Retry and timeout policy per asset. A retry must be safe; if it is not, fix
   the asset instead of adding retries.
5. An asset check for freshness and one for row-count sanity.
6. A failure path: make an asset fail, confirm the downstream assets do not
   run, and confirm the run is marked failed in the UI.

## Decisions to make yourself

| Decision | Why it is easy to get wrong |
|---|---|
| Partition key | Partitioning by load date makes backfills read the wrong files; partition by event date |
| Schedule timezone | A UTC cursor with a local schedule skips or repeats an hour around DST |
| Retry policy | Retrying a non-idempotent load duplicates rows |
| Asset vs op | Ops are implementation; assets are the contract other people depend on |
| Freshness | "The job ran" is not "the data is fresh"; check the maximum event time |
| Backfill semantics | A backfill must be able to run one day without changing the others |

## Done when

- The placeholder asset materialises and appears in the Dagster UI.
- The daily graph runs end to end from a clean core profile.
- A forced failure stops downstream assets and shows a failed run.
- A one-day backfill changes only that day's partition.
- `make check M=3` exists and fails on `main`, passes on `solutions`.

## Failure modes to watch

- **Schedule storm.** A schedule with no idempotency guard launches a run every
  minute and piles up duplicates.
- **Retry hides a bad key.** The job eventually succeeds because the second run
  appended a second copy; the table is now wrong.
- **Orphaned runs.** The daemon is down, the webserver still accepts launches,
  and nothing executes.
- **Timezone drift.** The partition for "yesterday" is computed in local time
  while events are UTC.
- **Silent skip.** A sensor that catches every exception looks healthy forever.

## Using AI on this module

Use AI to explain Dagster's partition and run-coordinator model, or to review a
retry policy. Write the asset graph and the partition key yourself. The graph
is the part that encodes your assumptions about time and dependency.
