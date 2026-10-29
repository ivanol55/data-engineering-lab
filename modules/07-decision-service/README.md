# Module 7 — Decision service

**Time:** 3–4 hours. **Profile:** `serving` + `stream`.

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

- `images/api/main.py`: FastAPI with `/health`, `/ready`, `/metrics` and a
  working `/decide`. The I/O, timeouts, idempotency cache and decision log are
  wired.
- `images/api/rules.py`: the pure rules. The first matching rule wins.
- `images/api/config.py`: the learner decisions. They are wrong on purpose.
- Valkey 9.0.7 with append-only persistence.
- The batch tables in Iceberg and, after module 6, streaming features in
  Valkey.
- Kafka for the decision log. The API publishes one event per decision.
- Lab-only fault injection: send `X-Lab-Fail-Dependency: postgres` or
  `valkey` to exercise the fail path without stopping a container.

## What you will build

1. Decide the missing-user rule. An unknown user is not a low-risk user.
2. Enable the account-status rule. A deleted or disabled account must never be
   allowed.
3. Enable the intel lookup and pick a TTL from the feed cadence. A fresh hit
   blocks; an expired hit does not.
4. Keep impossible travel as an MFA challenge, after the hard blocks.
5. Choose the fail mode for a Postgres or Valkey failure. A security decision
   should fail closed unless you can justify the opposite.
6. Turn on the Kafka decision log. The check matches the logged `request_id`
   with the response.
7. Measure p95 latency and keep the dependency budget below the caller's
   timeout.

## Your task

Edit `images/api/config.py`, rebuild the image, and run the check:

```bash
make build-api
make up P=serving
make check M=7
```

| Setting | Wrong value | What it breaks |
|---|---|---|
| `MISSING_USER_DECISION` | `"allow"` | an unknown user is treated as low risk |
| `CHECK_ACCOUNT_STATUS` | `False` | deleted and suspended accounts are allowed |
| `CHECK_INTEL` | `False` | a current indicator is ignored |
| `INTEL_TTL_SECONDS` | `86_400` | a stale indicator blocks for a day |
| `FAIL_MODE` | `"allow"` | a dependency outage opens the door |
| `DECISION_LOG_ENABLED` | `False` | decisions are fast and unauditable |

The reference TTL is 3600 seconds. The rules live in `images/api/rules.py`;
the config values decide which rules are active and what happens when data is
missing.

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

- `/decide` returns a decision and a reason for every request.
- A deleted or suspended user is never allowed, and neither is an unknown one.
- An intel hit inside its validity window is blocked; an expired hit is not.
- A Postgres or Valkey failure produces the documented fail mode, not a hang.
- Decision events appear on Kafka with the same request id as the response.
- p95 latency stays below the caller budget.
- `make check M=7` fails on `main`, passes on `solutions`.

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
