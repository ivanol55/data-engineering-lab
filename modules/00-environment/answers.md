# Module 0 answers

Answer in your own words. The check only requires that every question has an
answer under `### Your answer`, that it is long enough to contain a real
explanation, and that it mentions the key ideas. It does not grade prose.

If you are stuck, open the matching hint in `hints.md`. The hint gives a full
reference explanation; read it, close it, and then write your own version.

## Q1

**What this question is really asking:** can you tell the difference between
the data and the description of the data?

**What to cover:**

- Postgres owns the user rows;
- Lakekeeper owns the Iceberg table metadata;
- why those are separate responsibilities.

**Sentence starter:** “Postgres is the system of record because … Lakekeeper is
separate because …”

### Your answer

Postgres is the system of record for identity: it owns the user rows, their
roles, status, and timestamps, and it is the copy that the application writes
to. Lakekeeper is separate because it owns the Iceberg table metadata instead:
which tables exist, which metadata file is current, and what schema and
snapshots each table has. Keeping the address book out of the transactional
database means Postgres does not need to understand a table format, and several
engines can read the same Iceberg tables through one catalog.

## Q2

**What this question is really asking:** why is a folder of Parquet files not
a table?

**What to cover:** at least three of snapshots, schema evolution, partition
metadata, manifest/file pruning, time travel.

**Sentence starter:** “Iceberg adds a table layer on top of Parquet: …”

### Your answer

Iceberg adds a table layer on top of Parquet files. A snapshot records exactly
which files belong to the table at one committed version, so readers never
have to guess which files are current and writers can commit atomically. The
table also carries its own schema, which can evolve without rewriting every
file, and partition metadata that lets an engine skip files that cannot match a
query. Together those features give time travel, safe rollback, and file
pruning that a bare directory of Parquet cannot provide.

## Q3

**What this question is really asking:** when is a log a better integration
point than polling a database?

**What to cover:** buffering, decoupling producers and consumers, replay,
multiple consumers; the cost of another stateful system and delivery
complexity.

**Sentence starter:** “Kafka helps because … but it costs …”

### Your answer

Kafka helps because it buffers events between producers and consumers, so a
slow or restarted consumer does not force the producer to wait, and several
consumers can read the same stream independently. Because the log keeps the
records, a new consumer can replay history instead of asking the source for a
copy. The cost is another stateful system to run and secure, plus schema and
delivery work: “exactly once” is a property of the whole pipeline, not a box
you tick on the broker.

## Q4

**What this question is really asking:** why is “at least once” acceptable if
the write is idempotent?

**What to cover:** a retry can deliver the same record twice; a stable primary
key plus merge/upsert makes the second delivery replace the same logical row.

**Sentence starter:** “At-least-once means … A merge on a stable key makes the
retry safe because …”

### Your answer

At-least-once means a record is never silently lost, but a retry after a crash
can deliver the same record twice. If the sink writes with a stable primary key
and a merge or upsert, the second delivery replaces the same logical row
instead of adding a duplicate, so running the load twice leaves the table in
the same state. That is why the key matters more than the delivery guarantee:
an append with no key turns every retry into a new row.

## Q5

**What this question is really asking:** what does a partition buy you, and
when does it hurt?

**What to cover:** file pruning for date filters, cheaper retention; the cost
of many small files or queries that span every partition.

**Sentence starter:** “Partitioning by day helps when … It hurts when …”

### Your answer

Partitioning by day helps when queries filter on the event date, because the
engine can prune whole files instead of scanning the table, and retention
becomes a matter of dropping old partitions. It hurts when the partition key
creates too many tiny files, when queries span every date anyway, or when the
partition is much finer than the data volume justifies. A partition is a
physical layout decision, so it should follow the way the table is actually
queried and expired.

## Q6

**What this question is really asking:** why is a lab convenience not a
production recommendation?

**What to cover:** single node, no managed multi-AZ durability, S3
compatibility limits, operational burden.

**Sentence starter:** “SeaweedFS is fine for the lab because … It is not a
production object store because …”

### Your answer

SeaweedFS is fine for the lab because it is a single small service that speaks
the S3 API, stores the Parquet and metadata files locally, and needs no cloud
account or credentials. It is not a production object store because it runs as
a single node here, without managed multi-zone durability, and its S3
compatibility covers the operations this lab uses rather than every corner of
the API. In production you would also inherit backup, monitoring, and capacity
work that a managed store absorbs.

## Q7

**What this question is really asking:** what can health checks prove, and what
can they not prove?

**What to cover:** two things `make doctor` checks (Docker, RAM, ports,
container health, endpoints); two things it cannot check (data correctness,
duplicate keys, freshness, business rules).

**Sentence starter:** “`make doctor` checks … It cannot check …”

### Your answer

`make doctor` checks that Docker and Compose respond, that free RAM is enough
for the profile, that the host ports are not taken, and that the containers and
core endpoints are healthy. It cannot check whether the data is correct: a
duplicate key, a stale table, a dropped cursor, or a broken business rule all
look healthy to a process check. That is why the module checks exist, and why
“the container is up” is never the same statement as “the pipeline is right”.

## Q8

**What this question is really asking:** can you name a failure that still
looks healthy?

**What to cover:** one silent-failure example and the check that catches it,
for example appending a snapshot (row count doubles), dropping the cursor
(history reloads), or ignoring `deleted_at` (deleted users stay active).

**Sentence starter:** “One silent failure is … The check catches it by …”

### Your answer

One silent failure is loading the users snapshot with an append instead of a
merge: the job exits successfully, the table still answers queries, but every
user now appears twice and dashboards double-count them. The module 1 check
catches it by loading twice and asserting that the user id is unique and that
the second run replaced the changed row. Another example is a cursor reset,
which silently reloads history; the check catches that by comparing the row
count after a second load. The general lesson is that a pipeline can fail while
every process stays green.
