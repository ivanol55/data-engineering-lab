# Promotion and rollback

TODO(learner): write the rule that lets this model change a response, and the
rule that takes it back out. Offline AUC is not a promotion criterion.

The check looks for these sections:

- shadow: how long the model runs beside the rules without changing the
  response, and what you compare;
- promotion: the precision, block-rate and latency thresholds that must hold
  before the model can serve traffic;
- rollback: the signal, threshold and owner that removes the model, including
  the fail mode when the model service is unavailable.
