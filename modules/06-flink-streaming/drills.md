# Module 6 — Flink stream processing — drills

Break-it exercises. There is no answer key on purpose: the point is to
see the failure, then explain which invariant broke.

1. Switch the job from event time to processing time. Replay the same input twice and compare the window results.
2. Set allowed lateness to zero. Send an event just after its window closes and find where it disappears.
3. Disable checkpointing, kill the TaskManager, and restart. Compare the sink before and after.

Record what you observed, not just what you expected. A drill you
cannot reproduce is not finished.
