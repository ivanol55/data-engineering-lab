# Module 6 — Flink stream processing

**Time:** 4–5 hours. **Profile:** `stream` + `flink` + `serving`. **Status:** scaffold.

> Flink JobManager and TaskManager start with the `flink` profile. No job,
> exercise, or check exists yet.

## Goal

Score logins as they happen, using event time rather than arrival time. This is
where late data, watermarks, state size, and checkpointing stop being theory.

By the end you should have:

- a job that reads `login.events` from Kafka and emits a risk signal per event;
- a tumbling or sliding window over event time, with a watermark and allowed
  lateness you can defend;
- a keyed state store for per-user or per-IP behaviour;
- a join with the threat-intel stream that respects indicator validity;
- checkpointing to durable storage, and a restart that does not lose state;
- output to Valkey or another Kafka topic for the decision service.

## What already exists

- Flink 2.3.0, one JobManager and one TaskManager with two slots.
- Kafka from module 4. You need to produce events and create the intel topic.
- Valkey from the `serving` profile, if you choose it as a sink.
- The batch tables in Iceberg for a correctness comparison: a streaming result
  should agree with the batch result for the same window.

## What you will build

1. A source with event-time timestamps and a watermark strategy. Justify the
   out-of-orderness bound using the generator's behaviour.
2. A windowed aggregation: failures per user in the last N minutes, distinct
   source IPs per user, or velocity between countries.
3. A keyed process function with state. Decide the state TTL; unbounded state is
   a memory leak with a nice API.
4. A temporal join with threat intel. A regular join multiplies rows when the
   feed revises an indicator; decide how to keep one current version.
5. A sink to Valkey (low latency, overwrite) or Kafka (durable, replayable).
   Explain the delivery guarantee at the sink.
6. Checkpointing with a local filesystem or S3 path. Kill the TaskManager and
   show that the job recovers.

## Decisions to make yourself

| Decision | Why it is easy to get wrong |
|---|---|
| Time characteristic | Processing time makes results depend on when the job ran, not when the login happened |
| Watermark bound | Too tight drops late events; too loose delays every result |
| Allowed lateness | Zero is simple but silently discards the events the generator deliberately delays |
| State TTL | No TTL means state grows forever; too short means the feature is always cold |
| Join type | A regular stream-stream join retains both sides indefinitely and fans out on revisions |
| Sink semantics | At-least-once to Valkey is an overwrite; at-least-once to Kafka is a duplicate |

## Useful commands

```bash
make up P=stream,flink,serving
open http://localhost:8082
docker compose --profile flink logs -f flink-taskmanager
```

## Done when

- The job is `RUNNING` with a non-zero watermark.
- A late event inside the allowed lateness changes the window result; one
  outside it is dropped and visible in a metric.
- A TaskManager restart resumes from the checkpoint without duplicating the
  sink output.
- The streaming result for a completed window matches the batch query.
- `make check M=6` exists and fails on `main`, passes on `solutions`.

## Failure modes to watch

- **Processing time.** The same input produces different output on every run.
- **No watermark.** Windows never fire, or fire only when the source goes idle.
- **Unbounded state.** The TaskManager OOMs after a few hours of traffic.
- **Fan-out intel join.** One event becomes several because the feed has
  revisions.
- **Checkpoint without a durable path.** Recovery works until the container is
  recreated.

## Using AI on this module

Ask AI to explain watermark propagation or checkpoint barriers. Design the
window, the state key, and the lateness policy yourself. Those choices define
what "correct" means for this module.
