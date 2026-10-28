# Module 4 — Kafka and schemas — drills

Break-it exercises. There is no answer key on purpose: the point is to
see the failure, then explain which invariant broke.

1. Produce the same user's events with a null key. Inspect the partition assignment. What breaks in a per-user stateful consumer?
2. Set `acks=0` and kill the broker during a produce loop. Count what the producer thinks it sent and what the topic contains.
3. Enable consumer auto-commit and kill the consumer mid-batch. Restart it and look for skipped events.

Record what you observed, not just what you expected. A drill you
cannot reproduce is not finished.
