# Module 6 exercises

The job is `flink_jobs/risk_job.py`; the decisions are in
`flink_jobs/config.py`.

1. Start the profiles:

   ```bash
   make up P=stream,flink
   ```

2. Create the JSON topics and replay the fixtures:

   ```bash
   docker compose --profile tools run --rm tools python flink_jobs/setup.py reset
   docker compose --profile tools run --rm tools python flink_jobs/setup.py setup
   ```

   **Expect:** `produced 14000 events to login.events.json`.

3. Submit the job:

   ```bash
   docker compose --profile flink exec flink-jobmanager \
     flink run -m flink-jobmanager:8081 -d -py /workspace/flink_jobs/risk_job.py
   ```

4. Open <http://localhost:8082>, find `risk-signals`, and inspect the
   watermark and checkpoint counts.

5. Consume the output:

   ```bash
   docker compose --profile flink exec flink-jobmanager python3 -c "
   from confluent_kafka import Consumer
   c = Consumer({'bootstrap.servers': 'kafka:9092', 'group.id': 'debug',
                 'auto.offset.reset': 'earliest'})
   c.subscribe(['risk.signals'])
   for _ in range(20):
       m = c.poll(1)
       if m and m.value(): print(m.value().decode())
   "
   ```

6. Fix the values in `flink_jobs/config.py`:

   | Setting | Reference |
   |---|---|
   | `TIME_CHARACTERISTIC` | `"event"` |
   | `ALLOWED_LATENESS_SECONDS` | `10` |
   | `STATE_TTL_HOURS` | `24` |
   | `CHECKPOINTING` | `True` |

7. Cancel the job, resubmit it, and run `make check M=6`.

8. Drill: set `TIME_CHARACTERISTIC = "processing"`, resubmit, and compare the
   window keys with the fixture dates. Explain why they move.
