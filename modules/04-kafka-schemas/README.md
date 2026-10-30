# Module 4 — Kafka and schemas

**Time:** 3–4 hours. **Profile:** `stream`.

## What you are building towards

The batch path reads files. A login decision cannot wait for a nightly file, so
this module moves the same events onto a log. You will choose the partition
count, the message key, the producer's durability settings, the consumer's
commit point, and the schema compatibility rule, then prove each choice by
replaying the topic.

By the end you should have:

- a `login.events` topic with a deliberate partition count and key;
- a versioned Avro schema in Apicurio with a compatibility policy you can
  justify;
- a producer that is idempotent and sets `acks=all`;
- a consumer that commits offsets only after processing, and can replay without
  duplicating the sink;
- a documented answer to "what happens when a field is renamed?".

## Before you start

| Word | Plain meaning | In this module |
|---|---|---|
| **Topic** | A named, append-only log | `login.events` |
| **Partition** | A topic is split into ordered shards | Three partitions |
| **Offset** | The position of a record inside a partition | A consumer bookmark |
| **Key** | The value that chooses the partition | `user_id` |
| **Producer** | The process that writes records | `streaming/producer.py` |
| **Consumer** | The process that reads records | `streaming/consumer.py` |
| **Consumer group** | Consumers that share partitions | `login-events-sink` |
| **Lag** | How far a consumer is behind the log | Unread records |
| **`acks`** | How many replicas must confirm a write | `all` |
| **Idempotent producer** | The broker drops a duplicate retry | `enable.idempotence` |
| **Auto-commit** | The consumer commits offsets on a timer | Wrong for this sink |
| **Schema registry** | Stores the schema and checks compatibility | Apicurio |
| **Compatibility** | Which schema changes are allowed | `BACKWARD` |
| **Avro** | A binary record format with a schema | The message value |

The mental model is a set of numbered notebooks:

- A **topic** is a shelf of notebooks. Each **partition** is one notebook.
- A **record** is a line in a notebook, identified by its **offset** (line
  number).
- The **key** decides which notebook a line goes into. If the key is
  `user_id`, every event for one user is in the same notebook, in order.
- A **consumer group** is a team of readers; each notebook is assigned to one
  reader at a time.
- A **bookmark** is the committed offset. If you move the bookmark before you
  finish writing your notes, a crash loses work.

Kafka keeps the records after they are read. That is why replay is possible,
and why an idempotent sink is required.

## Guided walkthrough

### Step 1 — Create the topic and produce

```bash
make up P=stream
docker compose --profile tools run --rm tools python streaming/run.py reset
docker compose --profile tools run --rm tools python streaming/run.py setup
docker compose --profile tools run --rm tools python streaming/run.py produce
```

**You should see**, with the wrong config:

```
deleted topic, schema and sink
topic login.events: {'partitions': 1, 'error': None}
schema login.events-value: compatibility NONE
produced 14000 events
```

**What this proves:** the pipeline runs. It does not prove the topic is
designed for per-user processing or that a replay is safe.

### Step 2 — Look at the topic

Open Kafbat at <http://localhost:8087> and inspect `login.events`.

**You should see:** one partition and 14,000 records. In a single partition,
ordering is global, but you cannot add a second consumer to share the work.

### Step 3 — Replay twice and watch the sink double

```bash
docker compose --profile tools run --rm tools python streaming/run.py consume --replay
docker compose --profile tools run --rm tools python streaming/run.py consume --replay
docker compose --profile tools run --rm tools python -c \
  "print(sum(1 for line in open('/workspace/state/stream-sink.jsonl') if line.strip()))"
```

**You should see:** `28000`. The topic has 14,000 events; the sink has two
copies of each.

**What this proves:** a replay is not automatically safe. The sink must
deduplicate on `event_id`, or a consumer restart will double the output.

### Step 4 — Fix the seven values

Open `streaming/config.py` and set:

| Setting | Wrong | Reference |
|---|---|---|
| `PARTITION_COUNT` | `1` | `3` |
| `MESSAGE_KEY` | `None` | `"user_id"` |
| `ACKS` | `"1"` | `"all"` |
| `ENABLE_IDEMPOTENCE` | `False` | `True` |
| `AUTO_COMMIT` | `True` | `False` |
| `SCHEMA_COMPATIBILITY` | `"NONE"` | `"BACKWARD"` |
| `SINK_IDEMPOTENT` | `False` | `True` |

Then recreate the topic and replay:

```bash
docker compose --profile tools run --rm tools python streaming/run.py reset
docker compose --profile tools run --rm tools python streaming/run.py setup
docker compose --profile tools run --rm tools python streaming/run.py produce
docker compose --profile tools run --rm tools python streaming/run.py consume --replay
docker compose --profile tools run --rm tools python streaming/run.py consume --replay
docker compose --profile tools run --rm tools python -c \
  "print(sum(1 for line in open('/workspace/state/stream-sink.jsonl') if line.strip()))"
```

**You should see:** `topic login.events: {'partitions': 3, ...}`,
`compatibility BACKWARD`, and `14000` in the sink after both replays.

### Step 5 — Run the check

```bash
make check M=4
```

**You should see:** eight passing tests. The check reads the topic, asserts
three partitions, verifies that each user's events share one partition, replays
the sink, checks the committed offsets, and asks the registry to reject a field
rename and accept an optional field.

## The choice, explained

| Setting | What it controls | Why the reference is right |
|---|---|---|
| `PARTITION_COUNT = 3` | How many consumers can share the topic | Room for three consumers without changing per-user order |
| `MESSAGE_KEY = "user_id"` | Which partition a record goes to | Every event for a user stays on one partition, in order |
| `ACKS = "all"` | How many replicas confirm a write | The leader alone can acknowledge data it later loses |
| `ENABLE_IDEMPOTENCE = True` | Whether the broker drops duplicate retries | A producer retry must not create a second record |
| `AUTO_COMMIT = False` | When offsets are committed | Commit after the sink write, not on a timer |
| `SCHEMA_COMPATIBILITY = "BACKWARD"` | Which schema changes the registry accepts | New readers can read old data; a field rename is rejected |
| `SINK_IDEMPOTENT = True` | Whether a replay duplicates the output | The sink keys on `event_id` and overwrites |

**Why three partitions.** One partition cannot be shared by two consumers in
the same group, so a single slow consumer is the ceiling. Three gives room to
scale without turning ordering into a free-for-all. More partitions are not
free: each one costs file handles, rebalances, and metadata.

**Why key by `user_id`.** Kafka guarantees order only inside a partition. A
null key round-robins, so two events for the same user land on different
partitions and a per-user stateful operator sees them out of order. Keying by
`user_id` puts all of a user's events in one partition.

**Why `acks=all` and idempotence.** `acks=1` means the leader acknowledged the
write; if it fails before the followers copy it, the record is gone. `all`
waits for the in-sync replicas. An idempotent producer adds a sequence number
so a retry after a timeout is recognised as the same record. Idempotence
requires `acks=all`; the producer rejects the combination otherwise.

**Why no auto-commit.** Auto-commit runs on a timer. It can commit an offset
before the sink write finishes, so a crash loses the records between the commit
and the write. Commit after the write; a crash then replays a few records,
which is safe because the sink is idempotent.

**Why `BACKWARD`.** Backward compatibility means a consumer using the new
schema can read data written with the old one. Adding an optional field with a
default is compatible. Renaming a required field is not: old data has
`event_id`, the new reader requires `id`, and there is no default. `NONE`
accepts the rename silently, and every existing consumer breaks at runtime.

## Check yourself

<details>
<summary>What does a null key do to per-user ordering?</summary>

It lets the producer choose partitions round-robin (or by batch), so two events
for the same user can land on different partitions. Kafka only orders inside a
partition, so the consumer can see them out of order.

</details>

<details>
<summary>Why does an idempotent producer require `acks=all`?</summary>

The broker can only deduplicate a retry if it knows the original write reached
the in-sync replicas. With `acks=1`, a retry may arrive after a leader change
and the broker cannot guarantee the sequence. Kafka rejects the configuration
rather than pretend.

</details>

<details>
<summary>What is the difference between at-least-once and exactly-once here?</summary>

At-least-once means a record is never lost but may be delivered twice. The lab
accepts that and makes the sink idempotent on `event_id`. Exactly-once inside
Kafka does not cover the sink file, so the end-to-end guarantee still depends on
the sink.

</details>

<details>
<summary>Why does `BACKWARD` reject a rename but accept an optional field?</summary>

Backward compatibility asks whether a new reader can read old data. An optional
field with a default is absent in old data and gets the default. A renamed
required field has no value in old data, so the new reader cannot read it.

</details>

<details>
<summary>What happens to a consumer group when you add a partition?</summary>

Kafka rebalances the group and assigns the new partition to one consumer. Until
the rebalance finishes, consumers pause. That is why partition count is a design
decision, not a number to raise casually.

</details>

## Useful commands

```bash
docker compose --profile stream exec kafka \
  /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
docker compose --profile stream exec kafka \
  /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --describe --all-groups
curl -s http://localhost:8086/apis/registry/v3/system/info
```

## Done when

- The topic exists with three partitions and a `user_id` key.
- Every fixture event is in the topic exactly once, and replaying is safe for
  the sink.
- The registry rejects an incompatible change and accepts a compatible one.
- A consumer restart resumes from the committed offset, and lag returns to zero.
- `make check M=4` fails on `main`, passes on `solutions`.

## Failure modes to watch

- **Key by event id.** Ordering per user is lost; a per-user stateful operator
  sees interleaved events.
- **Auto-commit on.** The consumer commits offsets it has not processed.
- **Schema-less JSON.** A renamed field is silently null for every consumer.
- **Topic auto-creation.** A typo in the topic name creates a new topic and the
  consumer waits forever on an empty one.
- **Replay without idempotence.** The sink doubles every event and the row count
  still looks plausible.

## Using AI on this module

Ask AI to explain compatibility modes or to review a key/partition choice. Do
not let it choose the key, the commit point, or the compatibility policy for
you. Those are the decisions the module is testing.
