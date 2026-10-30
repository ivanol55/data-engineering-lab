# Module 9 — ML scoring — hints

These are progressive hints, one per hard decision. Open one at a time. The
decisions live in `ml/config.py`; retrain inside the MLflow container or run
`make check M=9`, which trains for you.

<details>
<summary>Hint 1: Cut features at the prediction time</summary>

For each feature, ask: could this value have been known before the login? A
count that includes the current event, or a status read after the decision, is
leakage. Join on time ranges, not on the current row.

Set `INCLUDE_CURRENT_EVENT = False`. The check recomputes `prior_failures` from
the fixture history and fails if any row counts the current event's failure.

</details>

<details>
<summary>Hint 2: Split by time</summary>

Sort by `event_time`, train on the first N days, validate on the next, test on
the last. A random split lets the same user and campaign appear on both sides.

Set `SPLIT_STRATEGY = "time"`. With seven fixture days and `TEST_DAYS = 1`, the
last day is the holdout and `train_end < test_start`.

</details>

<details>
<summary>Hint 3: Compare at the same threshold</summary>

The rules and the model must be compared at the same block rate or the same
false-positive budget. AUC alone does not tell you what happens to users.

Set `LOG_TO_MLFLOW = True` and `REGISTER_MODEL = True`. The run logs both the
model metrics and the `baseline_*` metrics on the same holdout, and the
registry version must point at the run the check just trained.

</details>

<details>
<summary>Hint 4: Shadow before promotion</summary>

A model that is better offline can still block more good users in production.
Run it beside the rules and compare per request before changing the response.

Set `SHADOW_MODE = True`. `ml/score.py` then returns the model decision and the
rule decision for the same input. Fill `ml/promotion.md` with a shadow window,
numeric promotion thresholds and an owner for rollback.

</details>
