# Module 7 — Decision service — hints

These are progressive hints, one per hard decision. Open one at a time.
The values live in `images/api/config.py`; rebuild the API image after each
change.

<details>
<summary>Hint 1: Write the fail mode down</summary>

For each dependency, choose fail-closed, fail-open, or degrade, and write the reason next to the code. A bare `except: return allow` is a security incident waiting for a review.

Set `FAIL_MODE = "block"`. The check injects a Postgres and a Valkey failure
with the `X-Lab-Fail-Dependency` header and expects `block` plus
`dependency_unavailable`.

</details>

<details>
<summary>Hint 2: Bound the cache by the feed</summary>

If threat intel updates hourly, a 24-hour TTL serves 23 hours of stale blocks. Pick a TTL from the update cadence and the cost of a stale decision.

Set `INTEL_TTL_SECONDS = 3_600` and `CHECK_INTEL = True`. The check writes a
fresh indicator and a two-hour-old indicator to Valkey and expects only the
fresh one to block.

</details>

<details>
<summary>Hint 3: Order rules by specificity</summary>

A broad `allow` rule first makes every later `block` unreachable. Put hard blocks first, then challenges, then the default allow. Test the order with one input per rule.

The order is already encoded in `rules.decide`: missing user, account status,
intel, impossible travel, default. Your job is to enable the checks and choose
`MISSING_USER_DECISION = "block"`. Then turn on `DECISION_LOG_ENABLED = True`
so every decision is auditable.

</details>
