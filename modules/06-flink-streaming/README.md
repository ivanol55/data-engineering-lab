# Module 6 — Flink stream processing

**Time:** 4–5 hours. **Profile:** `stream` + `flink` + `serving`.

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
- Kafka from module 4. Module 6 creates a JSON mirror topic (`login.events.json`)
  because Flink's Kafka connector reads JSON without a custom Avro deserialiser.
- `flink_jobs/risk_job.py` computes five-minute windows; `flink_jobs/setup.py`
  creates the topics and produces the fixtures.
- Valkey from the `serving` profile, if you choose it as a sink.
- The batch tables in Iceberg for a correctness comparison: a streaming result
  should agree with the batch result for the same window.

## What the job does

1. A source with event-time timestamps and a watermark strategy. Justify the
   out-of-orderness bound using the generator's behaviour.
2. A five-minute tumbling window with event counts, failures, distinct users
   and maximum risk. The check compares one window with a batch aggregation of
   the fixtures.
3. A state TTL for the keyed aggregation. Unbounded state is a memory leak with
   a nice API.
4. A Kafka sink for the window result. Explain what the sink duplicates when a
   window is retracted or the job restarts.
5. Checkpointing to a durable path. The check reads the completed checkpoint
   count from the Flink REST API.
6. Stretch: a temporal join with threat intel, and a sink to Valkey.

## Your task

Edit `flink_jobs/config.py`, then reset, submit and check:

```bash
make up P=stream,flink
python flink_jobs/setup.py reset
python flink_jobs/setup.py setup
docker compose --profile flink exec flink-jobmanager \
  flink run -m flink-jobmanager:8081 -d -py /workspace/flink_jobs/risk_job.py
make check M=6
```

| Setting | Wrong value | What it breaks |
|---|---|---|
| `TIME_CHARACTERISTIC` | `processing` | windows follow wall-clock time, not event time |
| `ALLOWED_LATENESS_SECONDS` | `0` | late events are silently dropped |
| `STATE_TTL_HOURS` | `0` | keyed state grows forever |
| `CHECKPOINTING` | `False` | a TaskManager restart loses state |

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

- The job is `RUNNING` and its output windows are keyed by event time.
- The streaming result for a completed window matches the batch aggregation.
- Checkpoints complete, and the state TTL and allowed lateness are non-zero.
- `make check M=6` fails on `main`, passes on `solutions`.

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
