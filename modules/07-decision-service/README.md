# Module 7 — Decision service

**Time:** 3–4 hours. **Profile:** `serving` + `stream`. **Status:** scaffold.

> The FastAPI process and Valkey start with the `serving` profile. `/health`
> and `/ready` work; `/decide` returns 501 on purpose. No rules, exercises, or
> checks exist yet.

## Goal

Serve a decision in milliseconds without lying about freshness. The service
must combine slow-moving identity data, fast-moving behaviour, and threat
intel, then write down why it decided what it decided.

By the end you should have:

- a `POST /decide` endpoint that returns `allow`, `mfa`, or `block` with a
  reason and a rule version;
- a Valkey lookup path with an explicit behaviour when the cache is cold or
  stale;
- a fallback when a dependency is down: fail closed, fail open, or degrade, and
  a written justification;
- a decision log on Kafka with the input, output, latency, and rule version;
- p95 latency measured, not guessed.

## What already exists

- `images/api/main.py`: FastAPI, `/health`, `/ready`, and a `/decide` that
  raises 501. `redis` and `psycopg` are installed.
- Valkey 9.0.7 with append-only persistence.
- The batch tables in Iceberg and, after module 6, streaming features in
  Valkey.
- Kafka for the decision log.

## What you will build

1. Replace the 501 with a rule pipeline. Start with three rules: deleted or
   disabled user, source IP on the current intel list, and impossible travel.
2. Define the feature contract: which features come from Valkey, which from
   Postgres, and how old each may be.
3. Implement a cold-cache path. A missing key is not "no risk"; decide whether
   to compute on demand, fall back to the batch table, or deny.
4. Add a dependency timeout budget. The total budget must be smaller than the
   caller's timeout.
5. Emit one decision event per request to Kafka, including the rule version.
   A decision without a log is not auditable.
6. Load-test with a fixed input distribution and report p50/p95/p99.

## Decisions to make yourself

| Decision | Why it is easy to get wrong |
|---|---|
| Default on missing data | Treating missing as `allow` is a silent bypass; treating it as `block` can take the service down |
| Cache TTL | Too long serves stale intel; too short puts Postgres on the hot path |
| Rule order | The first matching rule wins; a broad allow rule hides a later block |
| Feature time | A feature computed at request time is not reproducible from the log |
| Idempotency | A retried request must not log two decisions with different outcomes |
| Fail mode | Every dependency failure needs an explicit, written behaviour |

## Useful commands

```bash
make up P=serving
curl -s http://localhost:8001/health
curl -s http://localhost:8001/ready
curl -s -X POST http://localhost:8001/decide \
  -H 'content-type: application/json' \
  -d '{"user_id":"...","source_ip":"192.0.2.10"}'
```

## Done when

- `/decide` returns a decision and a reason for every fixture event.
- A deleted user is never allowed.
- An intel hit inside its validity window is blocked or challenged; an expired
  hit is not.
- Stopping Valkey produces the documented fail mode, not a hang.
- Decision events appear on Kafka with the same request id as the response.
- `make check M=7` exists and fails on `main`, passes on `solutions`.

## Failure modes to watch

- **Fail open by accident.** A caught exception returns `allow` and nobody
  notices until an incident review.
- **Stale intel.** The cache TTL outlives the feed's update cadence.
- **Rule shadowing.** An early `allow` makes a later `block` unreachable.
- **Unlogged decisions.** The service is fast and unauditable.
- **Timeout stacking.** Three 1-second dependency calls behind a 2-second
  caller timeout.

## Using AI on this module

Ask AI to review a fail-mode decision or a timeout budget. Write the rules and
the feature contract yourself. The service is the place where a plausible wrong
answer has a real security consequence.
