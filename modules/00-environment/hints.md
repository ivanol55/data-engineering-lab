# Module 0 hints

Open only after you have tried the exercise.

<details>
<summary>Q1 — system of record vs catalog</summary>

Postgres owns identity: users, roles, status, timestamps. Lakekeeper owns
Iceberg metadata: which tables exist, their schemas, snapshots, and manifest
lists. The data files live in SeaweedFS. Separating them means the application
database does not need to understand table formats, and the catalog can serve
many engines (Trino, DuckDB, pyiceberg) without copying rows.

</details>

<details>
<summary>Q2 — what Iceberg adds</summary>

A snapshot history with atomic commits, a schema that can evolve safely,
partition specs that can change, manifest files that let engines prune files,
and time travel. Plain Parquet gives you files and a schema embedded in each
file; it does not give you a table.

</details>

<details>
<summary>Q3 — Kafka trade-off</summary>

Kafka buffers events, decouples producers from consumers, allows replay, and
supports multiple consumers. The cost is another stateful system to operate,
schema compatibility work, and the fact that "exactly once" is an end-to-end
property, not a broker checkbox.

</details>

<details>
<summary>Q4 — at-least-once and idempotent writes</summary>

At-least-once means a consumer can see the same record again after a crash or
retry. If the target table has a stable key and the write is a merge/upsert, a
retry replaces the same logical row instead of appending a second copy. Without
a key, the duplicate is silent.

</details>

<details>
<summary>Q5 — daily partitions</summary>

Daily partitions let a query for one day skip every other day's files, and make
retention/drops cheap. They hurt when queries span many days, when the table is
tiny, or when the partition key has poor clustering and you create thousands of
small files.

</details>

<details>
<summary>Q6 — SeaweedFS</summary>

It is a single-node-friendly, all-in-one server aimed at simplicity. It is not
a managed multi-AZ service, its S3 compatibility has rough edges, and operating
it for durability, upgrades, and throughput is on you. Good for a laptop lab,
not for a production lakehouse.

</details>

<details>
<summary>Q7 — doctor's limits</summary>

It checks Docker/Compose, RAM, port conflicts, container health, and endpoint
reachability. It cannot tell you whether the pipeline logic is correct, whether
a table has duplicate keys, or whether the data is fresh.

</details>

<details>
<summary>Q8 — silent failure examples</summary>

Examples: appending a full user snapshot on every run (duplicates), forgetting
the incremental cursor (reloading history), or ignoring `deleted_at` (deleted
users stay active). The module 1 checks assert row counts, key uniqueness, the
changed status, and the deletion flag.

</details>
