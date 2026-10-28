# Module 0 stretch

Optional, not checked.

1. **Break a port on purpose.** Change `TRINO_PORT` in `.env` to a port already
   in use, run `make up P=core`, and read the error. Restore the value and run
   `make doctor` again. What did the failure tell you that `docker ps` would
   not?

2. **Add a role.** Insert a `security_analyst` role in Postgres, assign it to a
   user, and query it through Trino. What would break if the pipeline assumed
   the role list was fixed?

3. **Inspect an Iceberg table.** Use pyiceberg to print the schema, partition
   spec, and snapshot list of `raw.login_events` after module 1. Which snapshot
   property would you use to prove a load was idempotent?

4. **Measure the lab.** Run `docker stats --no-stream` with only `core` up.
   Compare it with the 8 GB per-module budget. Which service is the largest,
   and why is its JVM heap configured the way it is?

5. **Threat model the fixture.** The generator marks `is_attack` explicitly.
   In a real system you would not have that label at ingestion time. Which
   columns would you have to derive, and from what?
