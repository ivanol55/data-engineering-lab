# Module 9 — ML scoring — hints

These are progressive hints, one per hard decision. Open one at a time.

> This module is a scaffold: the exercises and checks are not implemented
> yet. The hints describe the decisions the module will test.

<details>
<summary>Hint 1: Cut features at the prediction time</summary>

For each feature, ask: could this value have been known before the login? A count that includes the current event, or a status read after the decision, is leakage. Join on time ranges, not on the current row.

</details>

<details>
<summary>Hint 2: Split by time</summary>

Sort by `event_time`, train on the first N days, validate on the next, test on the last. A random split lets the same user and campaign appear on both sides.

</details>

<details>
<summary>Hint 3: Compare at the same threshold</summary>

The rules and the model must be compared at the same block rate or the same false-positive budget. AUC alone does not tell you what happens to users.

</details>
