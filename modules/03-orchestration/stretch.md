# Module 3 — Orchestration with Dagster — stretch

Open-ended extensions. They are deliberately larger than one sitting and
have no reference solution.

1. Add a sensor that waits for a new daily fixture file and launches a partitioned run.
2. Add asset checks for freshness and row-count deviation, and make a failed check block downstream materialisation.
3. Run a three-day backfill from the UI and prove that only those three partitions changed.

Write down the trade-off you chose and the case where it would be the
wrong choice.
