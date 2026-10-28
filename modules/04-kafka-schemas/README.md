# Module 4 — Kafka and schemas

**Time:** 3–4 hours. **Profile:** `stream`. **Status:** scaffold.

> Kafka, Apicurio, Kafbat, and Debezium Connect start with the `stream`
> profile. Topics, schemas, producers, consumers, exercises, and checks are not
> written yet.

## Goal

Move login events onto a log instead of a folder of JSONL files. You will make
choices about keys, partitions, schema evolution, and delivery guarantees, then
prove them by replaying and re-reading the topic.

By the end you should have:

- a `login.events` topic with a deliberate partition count and key;
- a versioned schema in Apicurio, with a compatibility policy you can justify;
- a producer that is idempotent and sets `acks=all`;
- a consumer that commits offsets only after processing, and can replay a
  range without duplicating the output;
- a documented answer to "what happens when a field is renamed?".

## What already exists

- Kafka 4.4.0 in KRaft mode, one broker, host listener on `localhost:29092`
  and internal listener on `kafka:9092`.
- Apicurio Registry 3.3.3 on <http://localhost:8086>, using its embedded H2
  store. It is a lab registry, not a durable production one.
- Kafbat UI on <http://localhost:8081>.
- Debezium Connect on <http://localhost:8083> for module 5.
- The deterministic generator can produce the same events as the fixtures, so
  replay tests are repeatable.

Start with:

```bash
make up P=stream
docker compose --profile stream ps
```

## What you will build

1. Create the topic. Choose partitions based on the consumer parallelism you
   actually need, not on a round number.
2. Register an Avro or Protobuf schema. Decide the subject naming strategy
   (`topic-value` vs `record-value`) and the compatibility mode.
3. Produce the 14,000 fixture events. Key them so that all events for one user
   land on one partition, or explain why you chose a different key.
4. Consume them with a small Python consumer. Track lag, commit after process,
   and prove a replay does not duplicate the sink.
5. Evolve the schema: add an optional field, then rename one. Observe which
   change the registry rejects and why.
6. Kill the broker mid-produce and describe exactly which events may be
   duplicated or lost under your settings.

## Decisions to make yourself

| Decision | Why it is easy to get wrong |
|---|---|
| Message key | A null key round-robins events for one user across partitions, so per-user state is split |
| Partition count | More partitions is not free: rebalances, file handles, and ordering scope |
| `acks` / idempotence | `acks=1` loses the last records on leader failure; idempotent producers need `acks=all` |
| Consumer commit | Committing before processing loses events on crash; after processing duplicates them |
| Schema compatibility | `BACKWARD` allows new readers, not old ones; renaming a field is not a compatible change |
| Retention | A 7-day retention deletes the history you need for a backfill |

## Useful commands

```bash
docker compose --profile stream exec kafka \
  /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
docker compose --profile stream exec kafka \
  /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --all-groups
curl -s http://localhost:8086/apis/registry/v3/system/info
```

## Done when

- The topic exists with the partition count and key you chose.
- Every fixture event is in the topic exactly once, and replaying a range is
  safe for the sink.
- The schema registry rejects an incompatible change and accepts a compatible
  one.
- A consumer restart resumes from the committed offset, and lag returns to zero.
- `make check M=4` exists and fails on `main`, passes on `solutions`.

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
