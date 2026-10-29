# Module 7 exercises

The service is `images/api/`; the decisions are in `images/api/config.py`.
The image bakes the config in, so rebuild after every change.

1. Start the profiles:

   ```bash
   make up P=serving
   ```

2. Confirm the service and its dependencies:

   ```bash
   curl -s http://localhost:8001/health
   curl -s http://localhost:8001/ready
   ```

3. Pick an active user and send a request:

   ```bash
   make psql
   # select user_id, home_country from users
   #  where account_status = 'active' and deleted_at is null limit 1;
   ```

   ```bash
   curl -s -X POST http://localhost:8001/decide \
     -H 'content-type: application/json' \
     -d '{"user_id":"<uuid>","source_ip":"192.0.2.10","country":"Germany"}'
   ```

4. Seed threat intel in Valkey and repeat the request:

   ```bash
   docker compose --profile serving exec valkey \
     valkey-cli set "intel:192.0.2.10" "$(date +%s)"
   ```

   With the reference config the same request is blocked with
   `reason=threat_intel`.

5. Exercise the fail path without stopping a container:

   ```bash
   curl -s -X POST http://localhost:8001/decide \
     -H 'content-type: application/json' \
     -H 'X-Lab-Fail-Dependency: postgres' \
     -d '{"user_id":"<uuid>","source_ip":"192.0.2.10"}'
   ```

   A correct service returns `block` / `dependency_unavailable`.

6. Fix the values in `images/api/config.py`:

   | Setting | Reference |
   |---|---|
   | `MISSING_USER_DECISION` | `"block"` |
   | `CHECK_ACCOUNT_STATUS` | `True` |
   | `CHECK_INTEL` | `True` |
   | `INTEL_TTL_SECONDS` | `3600` |
   | `FAIL_MODE` | `"block"` |
   | `DECISION_LOG_ENABLED` | `True` |

7. Rebuild and run the check:

   ```bash
   make build-api
   make up P=serving
   make check M=7
   ```

8. Read the decision log:

   ```bash
   docker compose --profile stream exec kafka \
     /opt/kafka/bin/kafka-console-consumer.sh \
     --bootstrap-server localhost:9092 --topic login.decisions \
     --from-beginning --max-messages 5
   ```

   Every event must carry the same `request_id` as the response and the
   `rule_version` that produced it.

9. Drill: set `FAIL_MODE = "allow"`, rebuild, inject a Postgres failure, and
   explain why an outage becomes a bypass.
