# Module 0 drills

Short commands, one idea each. Run them from the repository root.

1. Show the Compose services and their health:

   ```bash
   make ps
   ```

2. Count users by status directly in Postgres:

   ```bash
   make psql
   ```

3. Count users through Trino's Postgres catalog:

   ```bash
   make query Q='SELECT account_status, count(*) FROM postgresql.public.users GROUP BY 1 ORDER BY 1'
   ```

4. List Iceberg schemas:

   ```bash
   make query Q='SHOW SCHEMAS IN iceberg'
   ```

5. Show the S3 bucket contents without leaving the terminal:

   ```bash
   docker compose --env-file .env --profile tools run --rm tools \
     python -c "import boto3; print(boto3.client('s3', endpoint_url='http://seaweedfs:8333', aws_access_key_id='labadmin', aws_secret_access_key='labadmin123', region_name='us-east-1').list_buckets())"
   ```

6. Ask Lakekeeper which warehouses exist:

   ```bash
   curl -s http://localhost:8181/management/v1/warehouse | python -m json.tool
   ```

7. Generate two days of events into `/tmp` and compare two runs:

   ```bash
   make generator ARGS="events --days 2 --out /tmp/day-a"
   make generator ARGS="events --days 2 --out /tmp/day-b"
   diff -r /tmp/day-a /tmp/day-b && echo deterministic
   ```

8. Count attacks by type in the fixture:

   ```bash
   python -c "import json,glob,collections; c=collections.Counter(json.loads(l)['attack_type'] for f in glob.glob('fixtures/events/*.jsonl') for l in open(f) if json.loads(l)['is_attack']); print(c)"
   ```

9. Find the busiest source IP in the fixtures.

10. Explain why `make doctor` passing does not mean the data is correct.
