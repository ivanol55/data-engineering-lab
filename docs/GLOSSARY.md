# Glossary

Every term here is used somewhere in the lab. Read the section for the module
you are on; you do not need to memorise the whole file first.

## The big picture

**Data engineering** is the work of moving data from the place where it is
created to the place where it is used, without losing it, duplicating it, or
quietly changing its meaning.

**System of record.** The authoritative copy of a fact. In this lab, Postgres
is the system of record for users and roles. If Postgres says a user is
disabled, that is the truth; a dashboard that says otherwise is stale.

**OLTP.** Online transaction processing. A database built for many small reads
and writes, such as "create this user" or "update this login". Postgres is the
OLTP system here.

**OLAP.** Online analytical processing. A system built for large scans and
aggregations, such as "how many attacks happened last week?". Trino and DuckDB
are the OLAP engines here.

**Batch.** Processing data in groups, usually on a schedule. Module 1 loads
seven daily files at once; module 2 rebuilds tables from those files.

**Stream.** Processing data continuously as each event arrives. Modules 4–6
move login events through Kafka and Flink.

**Pipeline.** The path data takes: source → extraction → storage → transform →
serving. A pipeline is correct only if every step preserves the meaning of the
data.

## Storage and tables

**Object storage.** A service that stores files by key, such as
`s3://lakehouse/warehouse/raw/users/...`. SeaweedFS plays this role locally.
It is cheap and durable, but it has no idea what a "row" or a "table" is.

**Data lake.** A collection of files in object storage. Without more structure,
it is easy to end up with a folder of Parquet files and no reliable table
definition.

**Lakehouse.** A data lake plus a table format and a catalog, so the files
behave like tables: schemas, snapshots, partitions, and SQL.

**Table format (Iceberg).** A specification for how to describe a table on top
of files. Iceberg stores metadata about which Parquet files belong to the table
at a given version. That metadata is what lets you query, update, and roll back
without guessing which files are current.

**Parquet.** A columnar file format. It stores data by column, which makes
analytical queries cheaper because the engine can read only the columns it
needs.

**Catalog.** The address book for tables. It maps a name such as
`iceberg.marts.fct_login_events` to the current Iceberg metadata file.
Lakekeeper is the catalog in this lab.

**Namespace / schema.** A folder-like grouping of tables. `raw` holds the
landing tables; `marts` holds the modelled tables.

**Snapshot.** An immutable version of an Iceberg table. A write creates a new
snapshot. Old snapshots are how Iceberg supports time travel and safe rollback.

**Partition.** A physical split of a table, usually by date. Partitioning by
`day(event_time)` lets a query skip every file that cannot contain the date it
needs. It also makes retention ("delete data older than 90 days") cheaper.

**Grain.** The meaning of one row. "One row per login event" is a grain. If a
join turns one event into three rows, the grain has changed even though the
table still looks fine.

## Moving data

**Extract, transform, load (ETL).** Pull data out, change it, then store it.
The lab mostly does ELT: load raw data first, transform it later with dbt.

**Full load.** Copy the whole source every time. Simple, but expensive at scale
and easy to duplicate if you append instead of replace.

**Incremental load.** Copy only what changed since the last run. It needs a
reliable cursor, such as `updated_at` or `event_time`, and a rule for late
data.

**Cursor.** The high-water mark that says "we have already loaded up to here".
A cursor on `event_time` can skip an event that arrives late with an older
timestamp.

**Idempotent.** Running the operation twice has the same effect as running it
once. A merge on a stable key is usually idempotent; an append is not.

**Upsert / merge.** Insert a row if the key is new, update it if the key
exists. This is how a mutable source such as Postgres users stays at one row
per user.

**Append.** Add rows without checking for duplicates. Correct for immutable
events if you also deduplicate or track a cursor; wrong for mutable snapshots.

**Deduplicate.** Remove repeated records. The key you deduplicate on must match
the grain you want.

**Late data.** An event whose timestamp is older than data you have already
processed. Batch pipelines often drop it silently; stream processors use
watermarks and allowed lateness to handle it.

## Streaming

**Event.** One fact that happened at a point in time, such as a login attempt.

**Topic.** A named, append-only log in Kafka. Producers write to it; consumers
read from it. Unlike a queue, reading does not remove the data.

**Partition.** A topic is split into partitions. Ordering is guaranteed only
inside one partition, not across the whole topic.

**Offset.** The position of a record inside a partition. A consumer commits an
offset to remember where it stopped.

**Key.** A value used to choose a partition. If you key by `user_id`, every
event for that user goes to the same partition, so per-user processing sees
them in order.

**Producer.** The process that writes records to Kafka.

**Consumer.** The process that reads records from Kafka.

**Consumer group.** A set of consumers that share the work. Each partition is
assigned to one consumer in the group at a time.

**Lag.** How far a consumer is behind the end of the log. High lag means the
consumer is slow or stopped.

**Delivery guarantee.** What happens on failure:
- *at most once*: a record may be lost, never duplicated;
- *at least once*: a record is never lost, but may be duplicated;
- *exactly once*: the ideal, but only inside a bounded system, not end to end.

**Tombstone.** A Kafka record with a null value. In a compacted topic it means
"delete this key". It is not the same as a row whose columns are null.

**Compaction.** Kafka keeps the latest record per key and eventually removes
older ones. Useful for "current state" topics; not a substitute for a
database.

**Schema registry.** A service that stores the schema for a topic and checks
whether a new schema is compatible with the old one. Apicurio plays this role.

**Compatibility.** The rule for schema changes. `BACKWARD` means a consumer
using the new schema can read old data. Renaming a field is not compatible
under most modes; adding an optional field usually is.

## Change data capture

**CDC.** Change data capture. Instead of polling a table every night, read the
database's write-ahead log and turn each insert, update, and delete into an
event.

**WAL.** Write-ahead log. Postgres writes every change to the WAL before it
changes the table. Logical replication reads a decoded form of that log.

**Replication slot.** A bookmark that tells Postgres how much WAL a consumer
still needs. An inactive slot makes WAL grow until the disk fills.

**Publication.** The set of tables that Postgres exposes for logical
replication.

**Snapshot.** In CDC, the initial copy of the existing rows before streaming
changes. Not the same word as an Iceberg snapshot; context matters.

**Debezium.** The connector that reads Postgres changes and writes them to
Kafka.

## Stream processing

**Event time.** When the event actually happened, according to its timestamp.

**Processing time.** When the stream processor happened to see the event. A
job that uses processing time produces different results depending on when it
ran.

**Window.** A finite slice of time, such as "five minutes". A tumbling window
does not overlap; a sliding window does.

**Watermark.** The processor's estimate of how far event time has advanced. It
is how the job decides a window is complete enough to emit.

**Allowed lateness.** How long the job keeps a window open after the watermark
passes, so late events can still update it.

**State.** Data the job remembers between events, such as a per-user counter.
State must be bounded, or it grows until the process runs out of memory.

**State TTL.** Time-to-live. After this period, idle state is discarded.

**Checkpoint.** A consistent snapshot of a stream job's state and position. It
is how the job recovers after a crash.

## Serving and reliability

**Cache.** A fast copy of data kept close to the serving path. Valkey is the
cache here. A cache is always a copy; you must decide what to do when it is
cold or stale.

**TTL.** Time-to-live. How long a cached value is allowed to live before it is
considered stale.

**Fail open.** If a dependency fails, allow the request. Convenient, and
dangerous for security decisions.

**Fail closed.** If a dependency fails, block the request. Safer, but an outage
can become a denial of service.

**p50 / p95 / p99 latency.** The latency below which 50%, 95%, or 99% of
requests finish. p95 is a common budget for user-facing services.

**Idempotency key.** A client-supplied id that lets the server return the same
answer for a retry instead of making a second decision.

**Decision log.** An append-only record of what the service decided and why.
Without it, you cannot audit or reproduce a decision.

## Observability and governance

**Metric.** A number sampled over time, such as row count or consumer lag.
Prometheus stores metrics.

**Freshness.** How old the newest data is. "The job ran" is not freshness;
"the newest event is two days old" is.

**Alert.** A rule that turns a metric into a page or a ticket. A useful alert
has a threshold, a duration, a severity, and a runbook.

**Runbook.** The steps an on-call person follows when an alert fires.

**Cardinality.** The number of distinct label combinations in a metric. A
`user_id` label creates one time series per user and can exhaust Prometheus.

**Catalogue.** The inventory of tables: owner, grain, retention, PII columns,
and upstream dependencies.

**PII.** Personally identifiable information, such as email, name, or a raw IP
address.

**Retention.** How long data is kept before deletion. Different systems can
have different clocks; a deletion request must reach all of them.

**Deletion procedure.** The ordered steps that remove a person's data from
every system, plus the verification that no copy remains.

## Machine learning

**Label.** The answer the model is trained to predict. Here it is `is_attack`,
which the generator knows but a real request would not.

**Leakage.** A feature that contains information from after the prediction
moment, or directly contains the label. Leakage makes offline metrics look
great and production results look bad.

**Point-in-time feature.** A feature computed using only data available before
the event being scored. "Prior failures" must not include the current event.

**Train/test split.** Dividing data into a part used to fit the model and a
part used to evaluate it.

**Time-based split.** Train on earlier dates and test on later dates. A random
split can put the same user or campaign on both sides, which leaks the future.

**Class imbalance.** When one label is rare. With 8% attacks, a model that
always says "allow" is 92% accurate and useless.

**Precision.** Of the events the model blocked, what fraction were really
attacks? Low precision means many false blocks.

**Recall.** Of the attacks, what fraction did the model catch? Low recall means
missed attacks.

**ROC AUC.** A ranking score: how well the model separates attacks from normal
events across all thresholds. It is useful for comparison, not for deciding a
block threshold by itself.

**Baseline.** A simple rule or previous model that a new model must beat. A
model that is worse than the existing rules is not an improvement.

**Shadow mode.** Run the model beside the existing rules and log both
decisions without changing the response. It is how you compare before
promoting.

**Promotion.** The decision to let a model affect real responses. It needs
offline thresholds, a shadow window, and a rollback rule.

**Rollback.** The procedure that removes a model from the serving path when a
metric crosses a threshold.
