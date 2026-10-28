# Module 8 — Consistency and governance — hints

These are progressive hints, one per hard decision. Open one at a time.

> This module is a scaffold: the exercises and checks are not implemented
> yet. The hints describe the decisions the module will test.

<details>
<summary>Hint 1: Freshness is max event time</summary>

`max(event_time)` compared with `now()` tells you whether the data is current. The last successful load time only tells you the job ran. Export both and alert on the first.

</details>

<details>
<summary>Hint 2: Keep labels bounded</summary>

Never put `user_id`, `event_id`, or a raw IP in a Prometheus label. Use a rule or a histogram. Estimate the series count before you add a label.

</details>

<details>
<summary>Hint 3: Alerts need a duration and a runbook</summary>

A threshold without `for:` flaps on every scrape. Add a duration, a severity, and a link to the action. Test the alert by breaking the pipeline on purpose.

</details>
