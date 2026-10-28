# Module 9 — ML scoring

**Time:** 4–6 hours. **Profile:** `ml` + `core`. **Status:** scaffold.

> MLflow starts with the `ml` profile and stores runs in Postgres with artifacts
> in SeaweedFS. No training code, feature pipeline, exercises, or checks exist
> yet.

## Goal

Replace part of the hand-written rule set with a model, without leaking the
future into training and without letting the offline metric lie about
production. The point is the pipeline around the model, not the algorithm.

By the end you should have:

- a point-in-time feature table keyed by `(user_id, event_time)`;
- a training set built only from data available before each label;
- a baseline rule score and a learned model compared on the same split;
- an MLflow run with params, metrics, and a registered model version;
- a batch or online scoring path with the same feature definitions as training;
- a rollout plan with a shadow mode and a rollback rule.

## What already exists

- MLflow 3.17.2 on <http://localhost:5001>, backed by the `mlflow` Postgres
  database and `s3://lakehouse/mlflow` for artifacts.
- The batch tables and, after module 2, the marts. `fct_login_events` already
  contains the outcome and the `is_attack` label.
- The decision service from module 7, which can call a model or stay on rules.

## What you will build

1. Define the label and the prediction moment. "Was this login an attack?" is
   only usable if every feature is known before the decision.
2. Build point-in-time features: user status at the time, prior failure count,
   IP reputation at the time, travel velocity. Join on time ranges, not on the
   current dimension row.
3. Split by time, not randomly. A random split puts future behaviour in the
   training set and inflates the metric.
4. Train a baseline (logistic regression or a small tree model) and compare it
   with the module 7 rules on the same holdout.
5. Log the run to MLflow, register the model, and record the feature list and
   the training window as metadata.
6. Score in shadow mode: log the model decision next to the rule decision
   without changing the response.
7. Choose a promotion rule and a rollback rule. Measure latency and the
   block-rate change, not only AUC.

## Decisions to make yourself

| Decision | Why it is easy to get wrong |
|---|---|
| Label | `is_attack` is ground truth from the generator; a real system would not have it at request time |
| Prediction time | A feature computed after the login leaks the outcome |
| Split | Random splits leak future users and future attacks into training |
| Class imbalance | 8% attacks makes accuracy useless; choose precision/recall for the cost of a false block |
| Train/serve skew | The training query and the online lookup must use the same definitions |
| Promotion | A better offline AUC can still increase false blocks in production |

## Useful commands

```bash
make up P=ml,core
open http://localhost:5001
```

## Done when

- The feature table has one row per event and no feature uses data after the
  event time.
- The time-based holdout is later than every training row.
- The MLflow run records the data window, the feature list, and the seed.
- Shadow scoring produces both decisions for the same request.
- The promotion and rollback rules are written down and testable.
- `make check M=9` exists and fails on `main`, passes on `solutions`.

## Failure modes to watch

- **Leakage.** A feature like "number of attacks by this user" includes the
  current attack and the model looks perfect offline.
- **Random split.** The holdout shares users and campaigns with training.
- **Accuracy on imbalanced data.** 92% accuracy by always predicting "allow".
- **Train/serve skew.** Training uses a 30-day window; serving reads a 5-minute
  cache with a different definition.
- **Silent model failure.** The model service times out and the API falls back
  to allow without logging it.

## Using AI on this module

Ask AI to review a feature for leakage or to explain a metric. Choose the
label, the prediction time, and the promotion rule yourself. Those are the
decisions that determine whether the model is useful or merely accurate.
