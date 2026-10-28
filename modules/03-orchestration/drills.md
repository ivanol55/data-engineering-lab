# Module 3 — Orchestration with Dagster — drills

Break-it exercises. There is no answer key on purpose: the point is to
see the failure, then explain which invariant broke.

1. Remove the retry policy and force a failure in the middle of the graph. Confirm downstream assets do not run and the run is failed.
2. Set the schedule to every minute with no idempotency guard. Watch duplicate loads appear, then explain which guard you would add.
3. Wrap an asset body in `try/except Exception: pass`. Materialise it with a broken input and observe how long the graph looks healthy.

Record what you observed, not just what you expected. A drill you
cannot reproduce is not finished.
