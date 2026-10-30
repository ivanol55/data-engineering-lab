# Module 6 — Flink stream processing

**Time:** 4–5 hours. **Profile:** `stream` + `flink`.

## What you are building towards

Modules 4 and 5 put events on a log. This module turns the log into risk
signals: every five minutes, how many logins happened, how many failed, how
many distinct users, and the highest risk score. The hard part is not the SQL.
It is deciding which clock the window follows, how long to wait for late
events, how much state to keep, and how to recover after a crash.

By the end you should have:

- a job that reads `login.events.json` and writes `risk.signals`;
- a five-minute tumbling window over event time;
- a watermark and an allowed-lateness bound you can defend;
- keyed state with a TTL;
- checkpointing to a durable path;
- a streaming result that agrees with a batch aggregation of the same window.

## Before you start

| Word | Plain meaning | In this module |
|---|---|---|
| **Event time** | When the login actually happened | The `event_time` column |
| **Processing time** | When the job happened to see the event | Wall-clock time |
| **Window** | A finite slice of time | Five-minute tumbling window |
| **Tumbling** | Non-overlapping windows | 00:00–00:05, 00:05–00:10 |
| **Watermark** | The job's estimate of how far event time has advanced | `event_time - 5 seconds` |
| **Allowed lateness** | How long a window stays open after the watermark passes | 10 seconds |
| **State** | What the job remembers between events | Counts per window |
| **State TTL** | When idle state is discarded | 24 hours |
| **Checkpoint** | A consistent snapshot of state and position | Every 5 seconds |
| **Parallelism** | How many copies of the job run | Two slots |

The mental model is a train timetable:

- **Event time** is the time printed on the ticket. **Processing time** is when
  the conductor checks it. A delayed train still belongs to its scheduled slot.
- A **window** is a platform announcement: "all trains scheduled between 00:00
  and 00:05".
- A **watermark** is the station clock. The announcement only plays when the
  clock passes the end of the window.
- **Allowed lateness** is the grace period for a passenger who arrives just
  after the announcement.
- A **checkpoint** is the station's written record of where every train is, so
  a power cut does not lose the day.

If the window follows processing time, the same fixture produces different
results on every run. If it follows event time, the 2026-09 fixtures always
produce the 2026-09 windows.

## Guided walkthrough

### Step 1 — Start the stream and Flink profiles

```bash
make up P=stream,flink
```

### Step 2 — Create the topics and load the fixtures

```bash
docker compose --profile tools run --rm tools python flink_jobs/setup.py reset
docker compose --profile tools run --rm tools python flink_jobs/setup.py setup
```

**You should see:** `produced 14000 events to login.events.json`.

`setup.py` creates `login.events.json` and `risk.signals`, then writes the
fixtures to the input topic with `user_id` as the key. The JSON mirror exists
because Flink's Kafka connector reads JSON without a custom Avro deserialiser.

### Step 3 — Submit the job with the wrong config

```bash
docker compose --profile flink exec flink-jobmanager \
  flink run -m flink-jobmanager:8081 -d -py /workspace/flink_jobs/risk_job.py
```

**You should see:** `Job has been submitted with JobID ...`.

Open the Flink UI at <http://localhost:8082> and confirm the job is `RUNNING`.

### Step 4 — Watch the output

```bash
docker compose --profile stream exec kafka \
  /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 --topic risk.signals --from-beginning
```

With `TIME_CHARACTERISTIC = "processing"`, the windows follow wall-clock time.
The fixture events happened in September, but the job is running now, so it
needs five minutes of wall-clock time before a window closes. The check gives
it 25 seconds and finds no windows.

Stop the consumer with Ctrl-C. This is the failure the module is about: the job
is healthy and the output is empty or dated today.

### Step 5 — Fix the five values

Open `flink_jobs/config.py` and set:

| Setting | Wrong | Reference |
|---|---|---|
| `TIME_CHARACTERISTIC` | `"processing"` | `"event"` |
| `WATERMARK_SECONDS` | `5` | `5` (already right) |
| `ALLOWED_LATENESS_SECONDS` | `0` | `10` |
| `STATE_TTL_HOURS` | `0` | `24` |
| `CHECKPOINTING` | `False` | `True` |

Cancel the running job, reset the topics, and submit again:

```bash
docker compose --profile flink exec flink-jobmanager flink list
docker compose --profile flink exec flink-jobmanager flink cancel <job-id>
docker compose --profile tools run --rm tools python flink_jobs/setup.py reset
docker compose --profile tools run --rm tools python flink_jobs/setup.py setup
docker compose --profile flink exec flink-jobmanager \
  flink run -m flink-jobmanager:8081 -d -py /workspace/flink_jobs/risk_job.py
```

### Step 6 — Read an event-time window

```bash
docker compose --profile stream exec kafka \
  /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 --topic risk.signals --from-beginning
```

**You should see** JSON records such as:

```json
{"window_start":"2026-09-01 00:00:00","window_end":"2026-09-01 00:05:00",
 "event_count":7,"failure_count":4,"distinct_users":7,"max_risk":33}
```

The first window has 7 events, 4 non-allow outcomes, 7 distinct users, and a
maximum risk score of 33. The exact order of the records is not guaranteed;
the counts are.

Stop the consumer with Ctrl-C.

### Step 7 — Check the checkpoint

```bash
curl -s http://localhost:8081/jobs/overview | python3 -m json.tool
```

Take the job id from the output and query its checkpoints:

```bash
curl -s http://localhost:8081/jobs/<job-id>/checkpoints | python3 -m json.tool
```

**You should see:** `"completed": 1` or more. A checkpoint that never completes
means the job cannot recover.

### Step 8 — Run the check

```bash
make check M=6
```

**You should see:** four passing tests. The check cancels stale jobs, resets
the topics, submits the job, compares one window with a batch aggregation of
the fixtures, and reads the checkpoint count from the REST API.

## The choice, explained

| Setting | What it controls | Why the reference is right |
|---|---|---|
| `TIME_CHARACTERISTIC = "event"` | Which clock the window follows | The fixtures are historical; event time makes the result reproducible |
| `WATERMARK_SECONDS = 5` | How far out of order the source may be | The generator's observed disorder is about five seconds |
| `ALLOWED_LATENESS_SECONDS = 10` | How long a window stays open after the watermark | The generator delays some events; zero drops them |
| `STATE_TTL_HOURS = 24` | How long idle keyed state is kept | Long enough for the feature, short enough to bound memory |
| `CHECKPOINTING = True` | Whether state and position are snapshotted | A TaskManager restart must recover, not restart from zero |

**Why event time.** Processing time makes the output depend on when the job
ran. Run it on a quiet afternoon and the windows are empty; run it during a
backfill and the windows mix September events with today's clock. Event time
puts each event in the window it belongs to.

**Why a five-second watermark.** The watermark says "I do not expect events
older than five seconds". A tighter bound drops the generator's deliberately
late events; a looser bound delays every window by that much. Five seconds is
the observed disorder of this feed, not a universal constant.

**Why ten seconds of lateness.** When the watermark passes the end of a window,
the window emits. Allowed lateness keeps its state for ten more seconds so a
late event can still update it. Zero is simple and silently discards exactly
the events the generator delays.

**Why state TTL.** The keyed aggregation remembers counts per window. Without a
TTL, state grows for every key forever, which is a memory leak with a nice API.
Twenty-four hours matches how long this feature is useful.

**Why checkpointing.** A checkpoint is a consistent snapshot of state and
Kafka position. Without it, a TaskManager restart loses the windows in flight
and the job cannot promise exactly-once processing.

## Check yourself

<details>
<summary>What happens to a window if the watermark never advances?</summary>

The window never fires, because the job never believes event time has passed
its end. A source that goes idle can leave the last windows open. Watermarks
need either continuing input or an idle-source strategy.

</details>

<details>
<summary>Why can processing time produce a different result on every run?</summary>

Because the window boundaries come from the wall clock, not from the event
timestamps. The same fixture lands in different windows depending on when the
job started and how fast it read the topic.

</details>

<details>
<summary>What does allowed lateness actually keep?</summary>

The window's state after it has emitted. A late event updates the state and can
produce an updated result. After the lateness period, the state is discarded and
a later event is dropped.

</details>

<details>
<summary>What does a checkpoint contain?</summary>

The job's keyed state and the source positions, written consistently so a
restart can resume from the same point. It does not contain the output topic;
the sink must be idempotent or transactional for end-to-end guarantees.

</details>

<details>
<summary>Why is the output compared with a batch aggregation?</summary>

Because the batch result is computed from the same fixtures with a simple
group-by. If the streaming window disagrees, the bug is in the window, the
watermark, or the lateness policy, not in the data.

</details>

## Useful commands

```bash
make up P=stream,flink
open http://localhost:8082
docker compose --profile flink logs -f flink-taskmanager
docker compose --profile flink exec flink-jobmanager flink list
```

## Done when

- The job is `RUNNING` and its output windows are keyed by event time.
- The streaming result for a completed window matches the batch aggregation.
- Checkpoints complete, and the state TTL and allowed lateness are non-zero.
- `make check M=6` fails on `main`, passes on `solutions`.

## Failure modes to watch

- **Processing time.** The same input produces different output on every run.
- **No watermark.** Windows never fire, or fire only when the source goes idle.
- **Unbounded state.** The TaskManager runs out of memory after a few hours.
- **Fan-out intel join.** One event becomes several because the feed has
  revisions.
- **Checkpoint without a durable path.** Recovery works until the container is
  recreated.

## Using AI on this module

Ask AI to explain watermark propagation or checkpoint barriers. Design the
window, the state key, and the lateness policy yourself. Those choices define
what "correct" means for this module.
