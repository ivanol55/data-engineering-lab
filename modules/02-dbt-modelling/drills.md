# Module 2 — dbt modelling — drills

Break-it exercises. There is no answer key on purpose: the point is to
see the failure, then explain which invariant broke.

1. Join `stg_login_events` to `stg_threat_intel` on `indicator` only. Count rows per `event_id`. Explain the number you see.
2. Remove the `unique` test on `event_id` and add `unique(event_id, indicator)`. Does the test still catch the fan-out?
3. Replace the incremental model with a view. Run it twice and compare the result with the incremental table. Which one is wrong after a late event?

Record what you observed, not just what you expected. A drill you
cannot reproduce is not finished.
