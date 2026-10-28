# Module 8 — Consistency and governance — drills

Break-it exercises. There is no answer key on purpose: the point is to
see the failure, then explain which invariant broke.

1. Add `user_id` as a label to the event counter and watch Prometheus memory and series count grow.
2. Remove the `for:` duration from an alert and trigger a one-scrape blip. Count how many notifications you get.
3. Stop the event loader for a day. Check whether any dashboard panel makes the staleness obvious without reading the logs.

Record what you observed, not just what you expected. A drill you
cannot reproduce is not finished.
