# Module 6 — Flink stream processing — hints

These are progressive hints, one per hard decision. Open one at a time.

> This module is a scaffold: the exercises and checks are not implemented
> yet. The hints describe the decisions the module will test.

<details>
<summary>Hint 1: Watermarks are a promise</summary>

A watermark says "no events older than this will arrive". Set the out-of-orderness bound from observed lateness, not from a guess. A tight bound fires windows early and drops late data.

</details>

<details>
<summary>Hint 2: State needs a lifetime</summary>

Every keyed value state entry lives until you clear it or set TTL. Estimate the key count and the per-key size, then choose a TTL that matches the feature's usefulness.

</details>

<details>
<summary>Hint 3: Constrain the intel join</summary>

A regular join keeps both sides and emits every match. For current intel, use a temporal join or keep a versioned map keyed by indicator with an interval. Count output rows per input event to prove there is no fan-out.

</details>
