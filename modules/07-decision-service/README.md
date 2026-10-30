# Module 7 — Decision service

**Time:** 3–4 hours. **Profile:** `serving` + `stream`.

## What you are building towards

Every login now needs an answer in milliseconds: allow it, challenge it with
MFA, or block it. The service must combine slow-moving identity data from
Postgres, fast-moving threat intel from Valkey, and the last country it saw for
the user. It must also write down why it decided, and it must behave in a
defined way when a dependency is down.

By the end you should have:

- a `POST /decide` endpoint that returns `allow`, `mfa`, or `block` with a
  reason and a rule version;
- a Valkey lookup path with an explicit behaviour when the cache is cold or
  stale;
- a fail mode for a Postgres or Valkey outage, with a written justification;
- a decision log on Kafka with the same `request_id` as the response;
- p95 latency measured, not guessed.

## Before you start

| Word | Plain meaning | In this module |
|---|---|---|
| **Serving path** | The code that answers a live request | FastAPI in `images/api` |
| **Cache** | A fast copy of data close to the request | Valkey |
| **TTL** | How long a cached value is trusted | `INTEL_TTL_SECONDS` |
| **Fail open** | Allow the request when a dependency fails | Dangerous for security |
| **Fail closed** | Block the request when a dependency fails | The reference |
| **Timeout budget** | The total time the dependencies may take | Below the caller's timeout |
| **Idempotency key** | A client id that makes a retry return the same answer | `request_id` |
| **Decision log** | An append-only record of what was decided and why | Kafka `login.decisions` |
| **Rule order** | The first matching rule wins | `rules.py` |
| **p95 latency** | The latency below which 95% of requests finish | Measured from `/metrics` |

The mental model is a bouncer at a door:

- **Postgres** is the guest list. It is authoritative but slow to check.
- **Valkey** is the note on the door: "this IP is on today's watch list" and
  "this guest was last seen in France". It is fast, and it can be stale.
- The **rule order** is the bouncer's instruction sheet. The first line that
  matches wins, so a broad "let everyone in" at the top hides every later
  check.
- **Fail closed** means: if the guest list cannot be read, do not guess.

The service is the one place in the lab where a plausible wrong answer has a
real security consequence. Treat the defaults as hostile.

## Guided walkthrough

### Step 1 — Build and start the service

```bash
make build-api
make up P=serving
curl -s http://localhost:8001/health
curl -s http://localhost:8001/ready
```

**You should see:** `{"status":"ok",...}` and a ready response with
`valkey: ok` and `postgres: ok`.

`/health` only proves the process is up. `/ready` checks the dependencies.

### Step 2 — Find an active user

```bash
docker compose exec -T postgres psql -U app -d app -tAc \
  "select user_id from users
    where account_status = 'active' and deleted_at is null
    order by user_id limit 1"
```

Copy the id. Clear any travel state for that user so the first call is simple:

```bash
docker compose exec -T valkey valkey-cli del last_country:<user-id>
```

### Step 3 — Ask for a decision with the wrong config

```bash
curl -s -X POST http://localhost:8001/decide \
  -H 'content-type: application/json' \
  -d '{"user_id":"<user-id>","source_ip":"192.0.2.10","country":"Germany"}'
```

**You should see** a response such as:

```json
{"request_id":"...","decision":"allow","reason":"default",
 "rule_version":"v1","latency_ms":8.2}
```

Now ask about a user that does not exist:

```bash
curl -s -X POST http://localhost:8001/decide \
  -H 'content-type: application/json' \
  -d '{"user_id":"11111111-1111-1111-1111-111111111111","source_ip":"192.0.2.12"}'
```

**You should see:** `"decision":"allow","reason":"unknown_user"`.

**What this proves:** an unknown user is being treated as low risk. Missing
identity data is not the same as a clean identity.

### Step 4 — See the intel and dependency failures

Set a fresh intel indicator and ask again:

```bash
docker compose exec -T valkey valkey-cli set intel:198.51.100.20 "$(date +%s)"
curl -s -X POST http://localhost:8001/decide \
  -H 'content-type: application/json' \
  -d '{"user_id":"<user-id>","source_ip":"198.51.100.20"}'
```

**You should see:** `allow`, because `CHECK_INTEL` is off.

Now inject a Postgres failure:

```bash
curl -s -X POST http://localhost:8001/decide \
  -H 'content-type: application/json' \
  -H 'x-lab-fail-dependency: postgres' \
  -d '{"user_id":"<user-id>","source_ip":"192.0.2.16"}'
```

**You should see:** `"decision":"allow","reason":"dependency_unavailable"`.
The service is failing open: an outage opens the door.

### Step 5 — Fix the six values

Open `images/api/config.py` and set:

| Setting | Wrong | Reference |
|---|---|---|
| `MISSING_USER_DECISION` | `"allow"` | `"block"` |
| `CHECK_ACCOUNT_STATUS` | `False` | `True` |
| `CHECK_INTEL` | `False` | `True` |
| `INTEL_TTL_SECONDS` | `86_400` | `3600` |
| `FAIL_MODE` | `"allow"` | `"block"` |
| `DECISION_LOG_ENABLED` | `False` | `True` |

The config is baked into the API image, so rebuild and restart:

```bash
make build-api
make up P=serving
```

### Step 6 — Re-run the same requests

```bash
# Unknown user: now blocked
curl -s -X POST http://localhost:8001/decide \
  -H 'content-type: application/json' \
  -d '{"user_id":"11111111-1111-1111-1111-111111111111","source_ip":"192.0.2.12"}'

# Fresh intel: blocked
docker compose exec -T valkey valkey-cli set intel:198.51.100.20 "$(date +%s)"
curl -s -X POST http://localhost:8001/decide \
  -H 'content-type: application/json' \
  -d '{"user_id":"<user-id>","source_ip":"198.51.100.20"}'

# Expired intel: allowed
docker compose exec -T valkey valkey-cli set intel:198.51.100.21 "$(( $(date +%s) - 7200 ))"
curl -s -X POST http://localhost:8001/decide \
  -H 'content-type: application/json' \
  -d '{"user_id":"<user-id>","source_ip":"198.51.100.21"}'
```

**You should see:** `block` / `threat_intel` for the fresh indicator, and
`allow` / `default` for the two-hour-old one.

### Step 7 — Check the metrics and the decision log

```bash
curl -s http://localhost:8001/metrics | grep -E 'lab_decisions_total|lab_decision_latency'
```

**You should see:** counters and a histogram. The p95 is computed by
Prometheus, not by the service; module 8 builds that query.

The decision log goes to Kafka. The check reads `login.decisions` and matches
the `request_id` with the response.

### Step 8 — Run the check

```bash
make check M=7
```

**You should see:** thirteen passing tests. The check talks to the running
container, not to the Python module, so it verifies the image you built.

## The choice, explained

| Setting | What it controls | Why the reference is right |
|---|---|---|
| `MISSING_USER_DECISION = "block"` | What happens when Postgres has no row | Unknown identity is not low risk |
| `CHECK_ACCOUNT_STATUS = True` | Whether deleted and inactive users are blocked | A deleted account must not be scored as active |
| `CHECK_INTEL = True` | Whether the Valkey watch list is consulted | A current indicator must block |
| `INTEL_TTL_SECONDS = 3600` | How long an indicator is trusted | The feed updates hourly; a day-old hit is stale |
| `FAIL_MODE = "block"` | What happens when a dependency fails | A security decision should fail closed |
| `DECISION_LOG_ENABLED = True` | Whether decisions are published to Kafka | A decision without a log is not auditable |

**Why block an unknown user.** A user id that Postgres has never seen is either
a bug, a deleted account, or an attacker. Treating it as low risk turns a data
problem into an access-control bypass.

**Why check the account status.** `deleted_at` and `account_status` are the
source's own statement that the account should not be used. Ignoring them means
a disabled account keeps working as long as its password does.

**Why a one-hour intel TTL.** The feed is refreshed hourly. A day-long TTL
means an indicator removed at 10:00 still blocks at 09:00 the next day. The TTL
is a statement about the feed's cadence, not a round number.

**Why fail closed.** If Postgres or Valkey is unreachable, the service cannot
know whether the user is valid or the IP is on the watch list. Allowing the
request makes the outage an access-control bypass. Blocking it turns the outage
into a denial of service, which is visible and recoverable; the alternative is
silent.

**Why log the decision.** The response is ephemeral; the log is the audit
trail. The `request_id` ties the two together, and the rule version says which
logic produced the answer.

**Why the timeouts matter.** The Postgres timeout is 1 second and the Valkey
timeout is 0.5 seconds. They must add up to less than the caller's timeout,
or the caller gives up while the service is still waiting.

## Check yourself

<details>
<summary>What is the difference between fail open and fail closed?</summary>

Fail open allows the request when a dependency fails; fail closed blocks it.
Fail open is convenient and dangerous for a security decision. Fail closed is
safer, but an outage becomes a denial of service, so it needs an incident path.

</details>

<details>
<summary>Why is a cache TTL a correctness decision, not a performance knob?</summary>

Because a cached value is a copy. If the TTL is longer than the source's update
cadence, the service serves a value the source has already changed. The TTL says
how stale an answer is allowed to be.

</details>

<details>
<summary>Why does the first matching rule win matter?</summary>

A broad early rule makes later rules unreachable. If `allow` is checked before
`deleted_user`, a deleted user is allowed and the later block never runs. Rule
order is part of the security contract.

</details>

<details>
<summary>What does the idempotency cache protect?</summary>

A retried request with the same `request_id` returns the same decision instead
of evaluating twice and possibly logging two different answers. The cache TTL
is short because the inputs can change.

</details>

<details>
<summary>What would you measure to know the service is healthy?</summary>

Request rate, decision mix, dependency error rate, and p95 latency. A service
that is up but failing closed for every request is healthy by `/health` and
useless in practice.

</details>

## Useful commands

```bash
make build-api
make up P=serving
curl -s http://localhost:8001/health
curl -s http://localhost:8001/ready
curl -s http://localhost:8001/metrics
```

## Done when

- `/decide` returns a decision and a reason for every request.
- A deleted, suspended, or unknown user is never allowed.
- A fresh intel hit is blocked; an expired hit is not.
- A Postgres or Valkey failure produces `block` / `dependency_unavailable`.
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
