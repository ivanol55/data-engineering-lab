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

TODO(learner): replace this line with your answer.

## Q2

**What this question is really asking:** why is a folder of Parquet files not
a table?

**What to cover:** at least three of snapshots, schema evolution, partition
metadata, manifest/file pruning, time travel.

**Sentence starter:** “Iceberg adds a table layer on top of Parquet: …”

### Your answer

TODO(learner): replace this line with your answer.

## Q3

**What this question is really asking:** when is a log a better integration
point than polling a database?

**What to cover:** buffering, decoupling producers and consumers, replay,
multiple consumers; the cost of another stateful system and delivery
complexity.

**Sentence starter:** “Kafka helps because … but it costs …”

### Your answer

TODO(learner): replace this line with your answer.

## Q4

**What this question is really asking:** why is “at least once” acceptable if
the write is idempotent?

**What to cover:** a retry can deliver the same record twice; a stable primary
key plus merge/upsert makes the second delivery replace the same logical row.

**Sentence starter:** “At-least-once means … A merge on a stable key makes the
retry safe because …”

### Your answer

TODO(learner): replace this line with your answer.

## Q5

**What this question is really asking:** what does a partition buy you, and
when does it hurt?

**What to cover:** file pruning for date filters, cheaper retention; the cost
of many small files or queries that span every partition.

**Sentence starter:** “Partitioning by day helps when … It hurts when …”

### Your answer

TODO(learner): replace this line with your answer.

## Q6

**What this question is really asking:** why is a lab convenience not a
production recommendation?

**What to cover:** single node, no managed multi-AZ durability, S3
compatibility limits, operational burden.

**Sentence starter:** “SeaweedFS is fine for the lab because … It is not a
production object store because …”

### Your answer

TODO(learner): replace this line with your answer.

## Q7

**What this question is really asking:** what can health checks prove, and what
can they not prove?

**What to cover:** two things `make doctor` checks (Docker, RAM, ports,
container health, endpoints); two things it cannot check (data correctness,
duplicate keys, freshness, business rules).

**Sentence starter:** “`make doctor` checks … It cannot check …”

### Your answer

TODO(learner): replace this line with your answer.

## Q8

**What this question is really asking:** can you name a failure that still
looks healthy?

**What to cover:** one silent-failure example and the check that catches it,
for example appending a snapshot (row count doubles), dropping the cursor
(history reloads), or ignoring `deleted_at` (deleted users stay active).

**Sentence starter:** “One silent failure is … The check catches it by …”

### Your answer

TODO(learner): replace this line with your answer.
