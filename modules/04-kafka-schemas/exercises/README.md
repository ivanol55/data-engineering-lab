# Module 4 exercises

The code is in `streaming/`; the decisions are in `streaming/config.py`.

1. Start the stream profile:

   ```bash
   make up P=stream
   ```

2. Create the topic and register the schema:

   ```bash
   docker compose --profile tools run --rm tools python streaming/run.py reset
   docker compose --profile tools run --rm tools python streaming/run.py setup
   ```

   **Expect:** `partitions: 1` and `compatibility NONE` with the wrong config.

3. Produce the fixtures:

   ```bash
   docker compose --profile tools run --rm tools python streaming/run.py produce
   ```

   **Expect:** `produced 14000 events`.

4. Consume, then replay twice, and count the sink:

   ```bash
   docker compose --profile tools run --rm tools python streaming/run.py consume --limit 1000
   docker compose --profile tools run --rm tools python streaming/run.py consume --replay
   docker compose --profile tools run --rm tools python streaming/run.py consume --replay
   docker compose --profile tools run --rm tools python -c \
     "print(sum(1 for line in open('/workspace/state/stream-sink.jsonl') if line.strip()))"
   ```

   **Expect with the wrong config:** `28000` lines for 14,000 events. With the
   reference config the same command prints `14000`.

5. Inspect the topic in Kafbat at <http://localhost:8087>. Check the partition
   count, the key of a few records, and the consumer group lag.

6. Fix the values in `streaming/config.py`:

   | Setting | Reference |
   |---|---|
   | `PARTITION_COUNT` | `3` |
   | `MESSAGE_KEY` | `"user_id"` |
   | `ACKS` | `"all"` |
   | `ENABLE_IDEMPOTENCE` | `True` |
   | `AUTO_COMMIT` | `False` |
   | `SCHEMA_COMPATIBILITY` | `"BACKWARD"` |
   | `SINK_IDEMPOTENT` | `True` |

   Recreate the topic and replay from step 2.

7. Run `make check M=4`.

8. Try the rename in the registry by hand: fetch the schema, rename `event_id`
   to `id`, and `PUT` it back. Under `BACKWARD` the registry must reject it.
   Then add an optional field with a default and confirm it is accepted. The
   module 4 check performs exactly this pair of changes and restores the
   canonical schema afterwards.
