# Module 5 — CDC with Debezium — drills

Break-it exercises. There is no answer key on purpose: the point is to
see the failure, then explain which invariant broke.

1. Drop tombstones with a topic setting and confirm the target keeps deleted users. Then restore them and fix the consumer.
2. Restart the connector with `snapshot.mode=initial` on an existing slot. Compare target and source row counts.
3. Stop the connector for ten minutes, write 10,000 rows, and watch `pg_wal` grow. Explain what would happen on a full disk.

Record what you observed, not just what you expected. A drill you
cannot reproduce is not finished.
