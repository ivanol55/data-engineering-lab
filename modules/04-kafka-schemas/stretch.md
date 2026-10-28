# Module 4 — Kafka and schemas — stretch

Open-ended extensions. They are deliberately larger than one sitting and
have no reference solution.

1. Create a compacted topic keyed by `user_id` and use it as a current-state store. Explain what compaction does and does not guarantee.
2. Implement a transactional producer and consumer, then describe the exact boundary where exactly-once still fails.
3. Write a schema migration plan for renaming `source_ip` to `src_ip` without breaking old consumers.

Write down the trade-off you chose and the case where it would be the
wrong choice.
