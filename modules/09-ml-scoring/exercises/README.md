# Module 9 exercises

The code is in `ml/`; the decisions are in `ml/config.py`. Training reads the
fixtures directly, so this module does not depend on the learner state of the
earlier batch modules.

1. Start the profiles:

   ```bash
   make up P=core,ml
   ```

2. Open MLflow at <http://localhost:5001>. There is no experiment yet; the
   wrong config does not log anything.

3. Build the features by hand and look for the leak:

   ```bash
   docker compose --profile core --profile ml run --rm \
     --workdir /workspace --entrypoint python mlflow -c '
   from ml import features
   frame = features.build_features()
   print(frame[["prior_events", "prior_failures", "is_attack"]].head())
   '
   ```

   For an event whose `outcome` is not `allow`, `prior_failures` must not
   include that event. If it does, the model is reading the answer.

4. Train once with the wrong config and read the summary:

   ```bash
   docker compose --profile core --profile ml run --rm \
     --workdir /workspace --entrypoint python mlflow python ml/train.py
   ```

   The `run_id` is `null` and the split is random, so `train_end` is later
   than `test_start`.

5. Fix the values in `ml/config.py`:

   | Setting | Reference |
   |---|---|
   | `SPLIT_STRATEGY` | `"time"` |
   | `INCLUDE_CURRENT_EVENT` | `False` |
   | `LOG_TO_MLFLOW` | `True` |
   | `REGISTER_MODEL` | `True` |
   | `SHADOW_MODE` | `True` |

6. Retrain and inspect the run:

   ```bash
   docker compose --profile core --profile ml run --rm \
     --workdir /workspace --entrypoint python mlflow python ml/train.py
   ```

   The run records the feature list, the seed, the train/test windows, the
   model metrics and the `baseline_*` metrics. The registry has a new
   `login-risk` version whose source run is this run.

7. Score one request in shadow mode:

   ```bash
   docker compose --profile core --profile ml run --rm \
     --workdir /workspace --entrypoint python mlflow python ml/score.py \
     --user-id 00000000-0000-0000-0000-000000000004 \
     --event-time 2026-09-07T12:00:00Z \
     --source-ip 203.0.113.10 \
     --country Germany \
     --device-id dev-1 \
     --risk-score 80
   ```

   The output contains both `model_decision` and `rule_decision`.

8. Write `ml/promotion.md`. It needs `## Shadow`, `## Promotion` and
   `## Rollback`, numeric thresholds, a latency budget and an owner. "Better
   AUC" is not a rollout rule.

9. Run the check:

   ```bash
   make check M=9
   ```

10. Drill: set `INCLUDE_CURRENT_EVENT = True`, retrain, and compare the
    holdout precision with the clean run. Explain why the leaked feature is
    unavailable at request time.
