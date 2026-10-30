# Module 9 — ML scoring

**Time:** 4–6 hours. **Profile:** `ml` + `core`.

## What you are building towards

Modules 1–8 built the data and the rules. This module replaces part of the rule
set with a model, without leaking the future into training and without letting
an offline metric lie about production. The point is the pipeline around the
model, not the algorithm: the features, the split, the run record, the registry,
the shadow comparison, and the rollback rule.

By the end you should have:

- a point-in-time feature table with one row per event;
- a chronological train/test split;
- a baseline rule score and a learned model compared on the same holdout;
- an MLflow run with params, metrics, and a registered model version;
- a shadow scoring path that returns both decisions;
- a promotion and rollback plan with measurable thresholds.

## Before you start

| Word | Plain meaning | In this module |
|---|---|---|
| **Label** | The answer the model predicts | `is_attack` |
| **Feature** | An input the model may use | `prior_failures`, `risk_score` |
| **Leakage** | A feature that contains the answer or future information | Counting the current event's failure |
| **Point-in-time** | Computed using only data available before the event | `prior_failures` before this login |
| **Train/test split** | Fit on one part, evaluate on another | 6 days train, 1 day test |
| **Time-based split** | Train on earlier dates, test on later ones | The last day is the holdout |
| **Class imbalance** | One label is rare | About 8% of events are attacks |
| **Precision** | Of the blocks, how many were real attacks | Low precision = false blocks |
| **Recall** | Of the attacks, how many were caught | Low recall = missed attacks |
| **ROC AUC** | How well the model ranks attacks above normal events | Useful for comparison, not a threshold |
| **Baseline** | A simple rule the model must beat | `risk_score >= 70` |
| **Shadow mode** | Log the model decision without changing the response | Compare before promoting |
| **MLflow run** | A record of params, metrics, and artifacts | One per training |
| **Model registry** | Versions of a model, each tied to a run | `login-risk` |

The mental model is predicting an exam result:

- The **label** is the final grade. You do not get it until after the exam.
- A **feature** is what you knew before the exam: attendance, previous grades.
- **Leakage** is using the final grade as an input. The model looks perfect and
  learns nothing useful.
- A **random split** puts the same student in both the practice set and the
  exam. A **time split** trains on last term and tests on this term.
- **Accuracy** is a bad headline when 92% of students pass; a model that says
  "pass" to everyone is 92% accurate and useless.
- **Shadow mode** is grading the model's exam beside the real one, without
  changing anyone's result.

## Guided walkthrough

### Step 1 — Start MLflow

```bash
make up P=core,ml
```

Open <http://localhost:5001>. The experiment list is empty until the first
tracked run.

### Step 2 — Train with the wrong config

```bash
docker compose --profile core --profile ml run --rm \
  --workdir /workspace --entrypoint python mlflow ml/train.py
```

**You should see** a JSON summary with:

```
"run_id": null,
"metrics": {
  "accuracy": 0.9996,
  "precision": 0.9958,
  "recall": 1.0,
  "roc_auc": 0.99995
},
"params": {
  "split_strategy": "random",
  "include_current_event": "True",
  ...
  "train_rows": 11200,
  "test_rows": 2800
}
```

**What this proves:** the model is almost perfect, and that is the bug.
`prior_failures` counts the current event's failure, so the model is told the
answer. The random split also puts the same users on both sides. `run_id` is
`null`, so nothing was recorded and nothing can be promoted.

### Step 3 — Fix the five values

Open `ml/config.py` and set:

| Setting | Wrong | Reference |
|---|---|---|
| `SPLIT_STRATEGY` | `"random"` | `"time"` |
| `INCLUDE_CURRENT_EVENT` | `True` | `False` |
| `LOG_TO_MLFLOW` | `False` | `True` |
| `REGISTER_MODEL` | `False` | `True` |
| `SHADOW_MODE` | `False` | `True` |

Train again:

```bash
docker compose --profile core --profile ml run --rm \
  --workdir /workspace --entrypoint python mlflow ml/train.py
```

**You should see:**

```
"run_id": "<uuid>",
"params": {
  "split_strategy": "time",
  "include_current_event": "False",
  "train_start": "2026-09-01 ...",
  "train_end": "2026-09-06 ...",
  "test_start": "2026-09-07 ...",
  "test_end": "2026-09-07 ...",
  "train_rows": 12000,
  "test_rows": 2000
}
```

The training window ends before the holdout starts, and the last day is the
test set. Open MLflow and confirm the run, its params, its metrics, and the
registered `login-risk` version.

### Step 4 — Score in shadow mode

Training writes `/tmp/de-lab-ml/model.pkl` inside the container. `/tmp` is not
shared between one-off containers, so run training and scoring in the same
container:

```bash
docker compose --profile core --profile ml run --rm \
  --workdir /workspace --entrypoint sh mlflow -c \
  "python ml/train.py >/tmp/train.out && \
   python ml/score.py \
     --user-id 00000000-0000-0000-0000-000000000004 \
     --event-time 2026-09-07T12:00:00Z \
     --source-ip 203.0.113.10 \
     --country Germany \
     --device-id dev-1 \
     --risk-score 80"
```

**You should see** a JSON line such as:

```json
{"model_score":0.93,"model_decision":"block","shadow":true,
 "rule_decision":"block"}
```

`shadow: true` means the model decision was logged beside the rule decision
without changing the response.

### Step 5 — Write the promotion plan

Open `ml/promotion.md`. It needs three sections:

- `## Shadow`: how long the model runs beside the rules, and what you compare.
- `## Promotion`: the precision, block-rate, and latency thresholds.
- `## Rollback`: the signal, threshold, and owner that removes the model.

Use measurable numbers, not "better AUC". For example: precision at least
0.90, recall at least 0.85, block rate within 2 percentage points of the
baseline, p95 latency below 250 ms, and rollback below 0.80 precision or above
500 ms p95.

### Step 6 — Run the check

```bash
make check M=9
```

**You should see:** seven passing tests. The check trains inside the MLflow
image, verifies the point-in-time features, the chronological split, the run
contract, the registered version, shadow scoring, and the promotion plan.

## The choice, explained

| Setting | What it controls | Why the reference is right |
|---|---|---|
| `SPLIT_STRATEGY = "time"` | How rows are divided | The holdout is later than every training row, so the future is not in training |
| `INCLUDE_CURRENT_EVENT = False` | Whether the current outcome is a feature | The current event's failure is the label; including it is leakage |
| `LOG_TO_MLFLOW = True` | Whether the run is recorded | A run that is not tracked cannot be compared or promoted |
| `REGISTER_MODEL = True` | Whether the model gets a registry version | Serving by version needs a registered artifact |
| `SHADOW_MODE = True` | Whether the model decision is logged beside the rules | Compare before changing the response |

**Why a time split.** A random split puts the same user, device, and attack
campaign on both sides. The model memorises the user and the holdout is no
longer a test of the future. The last day is the closest thing this fixture has
to "next week".

**Why no current event.** `prior_failures` must count failures strictly before
the event. Including the current failure is the answer key. The check
recomputes the expected value event by event and fails if any row disagrees.

**Why MLflow.** A metric printed to a terminal is not reproducible. The run
records the split, the feature list, the seed, the date window, and the row
counts, and the registry ties a version to that run. The check compares the
latest registered version's `run_id` with the run it just trained, so a stale
registry cannot pass.

**Why shadow mode.** Offline metrics are computed on a historical holdout. A
model can look better offline and still increase false blocks in production.
Shadow mode logs both decisions on live traffic without changing the response,
so you can compare precision, recall, block rate, and latency before promoting.

**Why a written rollback.** A promotion without a rollback is a one-way door.
The plan names the signal (precision, block rate, latency, error rate), the
threshold, the owner, and the fail mode when the model service is unavailable.

## Check yourself

<details>
<summary>What is leakage, in one sentence?</summary>

A feature that contains information from after the prediction moment, or
directly contains the label. It makes offline metrics look great and production
results look bad.

</details>

<details>
<summary>Why is accuracy misleading with 8% attacks?</summary>

A model that always predicts "allow" is 92% accurate and catches no attacks.
Precision and recall describe the errors that matter: false blocks and missed
attacks.

</details>

<details>
<summary>Why is a random split wrong for this dataset?</summary>

Because the same user, device, or campaign can appear in both training and the
holdout. The model memorises the entity instead of learning behaviour, and the
holdout no longer represents the future.

</details>

<details>
<summary>What does the model registry add over a saved file?</summary>

A version, a link to the training run, and an artifact source. Serving by
version lets you roll back to a known run instead of guessing which file is
current.

</details>

<details>
<summary>Why can a model with better AUC be worse in production?</summary>

AUC measures ranking across all thresholds. The production decision uses one
threshold, and a better ranking can still produce more false blocks at that
threshold. Precision, block rate, and latency on live traffic decide.

</details>

## Useful commands

```bash
make up P=core,ml
open http://localhost:5001
docker compose --profile core --profile ml run --rm \
  --workdir /workspace --entrypoint python mlflow ml/train.py
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
