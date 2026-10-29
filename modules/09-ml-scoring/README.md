# Module 9 — ML scoring

**Time:** 4–6 hours. **Profile:** `ml` + `core`.

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
- `ml/features.py`: point-in-time features built from `fixtures/events`. It
  reads the fixtures directly, so the exercise does not depend on the learner
  state of modules 1 and 2.
- `ml/train.py`: the logistic-regression pipeline, the rule baseline, and the
  MLflow run. The learner decisions are in `ml/config.py`.
- `ml/score.py`: the serving path and the shadow comparison.
- `ml/promotion.md`: the rollout plan. It is a placeholder on `main`.
- The batch tables and, after module 2, the marts. `fct_login_events` already
  contains the outcome and the `is_attack` label.
- The decision service from module 7, which can call a model or stay on rules.

## Your task

Start the profiles:

```bash
make up P=core,ml
```

Fix the decisions in `ml/config.py`, then retrain and run the check:

```bash
make check M=9
```

| Setting | Wrong value | What it breaks |
|---|---|---|
| `SPLIT_STRATEGY` | `"random"` | the holdout shares users and campaigns with training |
| `INCLUDE_CURRENT_EVENT` | `True` | `prior_failures` includes the outcome being predicted |
| `LOG_TO_MLFLOW` | `False` | the run cannot be compared, reproduced or promoted |
| `REGISTER_MODEL` | `False` | the model cannot be served by version |
| `SHADOW_MODE` | `False` | the model decision is never compared with the rules |

The reference values are `"time"`, `False`, `True`, `True` and `True`. The
check trains once, then verifies the feature table, the chronological split,
the MLflow run and registry, the shadow score, and `ml/promotion.md`.

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
- The latest registered `login-risk` version points at the run just trained.
- Shadow scoring produces both decisions for the same request.
- The promotion and rollback rules are written down and testable.
- `make check M=9` fails on `main`, passes on `solutions`.

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
