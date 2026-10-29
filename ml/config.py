"""Module 9 learner decisions.

The training script still runs with the values below; it just leaks the
current event into the features, splits randomly, and never records the run.
Change one value, retrain, and run ``make check M=9``.
"""

# TODO(learner): a random split puts future users and campaigns in the
# training set. Use "time" and keep the last day as the holdout.
SPLIT_STRATEGY = "random"

# TODO(learner): counting the current event's failure in `prior_failures` is
# leakage: the model is told the answer. Turn this off.
INCLUDE_CURRENT_EVENT = True

# TODO(learner): a run that is not in MLflow cannot be compared, reproduced or
# promoted. Turn tracking on.
LOG_TO_MLFLOW = False

# TODO(learner): a model that is not registered cannot be served by version.
REGISTER_MODEL = False

# TODO(learner): shadow mode logs the model decision next to the rule
# decision. Turn it on before changing what the API returns.
SHADOW_MODE = False

# The holdout is the last day of the fixture window.
TEST_DAYS = 1
RANDOM_SEED = 1337

MODEL_NAME = "login-risk"
EXPERIMENT_NAME = "module-09-login-risk"

# The MLflow image mounts the repo read-only; local artefacts go to /tmp.
MODEL_PATH = "/tmp/de-lab-ml/model.pkl"
RUN_PATH = "/tmp/de-lab-ml/run.json"
