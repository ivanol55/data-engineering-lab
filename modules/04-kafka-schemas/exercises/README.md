# Module 4 exercises

The code is in `streaming/`; the decisions are in `streaming/config.py`.

1. Start the stream profile:

   ```bash
   make up P=stream
   ```

2. Create the topic and register the schema:

   ```bash
   python streaming/run.py reset
   python streaming/run.py setup
   ```

3. Produce the fixtures:

   ```bash
   python streaming/run.py produce
   ```

4. Consume with a new group, then replay with another group:

   ```bash
   python streaming/run.py consume --limit 1000
   python streaming/run.py consume --replay --limit 1000
   ```

   With the reference config the second command writes no duplicate
   `event_id`s to `state/stream-sink.jsonl`.

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

7. Run `make check M=4`.

8. Try the rename in the registry by hand: fetch the schema, rename
   `event_id` to `id`, and `PUT` it back. Under `BACKWARD` the registry must
   reject it. Then add an optional field with a default and confirm it is
   accepted.
