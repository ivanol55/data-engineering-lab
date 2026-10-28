# Module 7 — Decision service — hints

These are progressive hints, one per hard decision. Open one at a time.

> This module is a scaffold: the exercises and checks are not implemented
> yet. The hints describe the decisions the module will test.

<details>
<summary>Hint 1: Write the fail mode down</summary>

For each dependency, choose fail-closed, fail-open, or degrade, and write the reason next to the code. A bare `except: return allow` is a security incident waiting for a review.

</details>

<details>
<summary>Hint 2: Bound the cache by the feed</summary>

If threat intel updates hourly, a 24-hour TTL serves 23 hours of stale blocks. Pick a TTL from the update cadence and the cost of a stale decision.

</details>

<details>
<summary>Hint 3: Order rules by specificity</summary>

A broad `allow` rule first makes every later `block` unreachable. Put hard blocks first, then challenges, then the default allow. Test the order with one input per rule.

</details>
