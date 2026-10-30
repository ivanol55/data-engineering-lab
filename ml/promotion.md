# Promotion and rollback

## Shadow

Run the model beside the module 7 rules for 14 days and log both decisions for
every request without changing the response. Compare precision, recall, block
rate, and p95 latency on the same traffic, split by attack type. A shadow run
that only compares AUC is not evidence: the rules and the model can rank events
similarly while disagreeing on the block threshold.

Promotion requires at least 10,000 shadowed requests and 200 labelled attacks,
so the confidence interval on precision is narrow enough to act on. The owner
of the security-analytics on-call rota signs off on the comparison.

## Promotion

The model may replace the rule decision only when all of these hold on the
shadow window:

- precision at the chosen threshold is at least 0.90, so fewer than 10% of
  blocks are false;
- recall is at least 0.85, so the model does not miss more attacks than the
  rules;
- the block rate stays within 2 percentage points of the rule baseline, so the
  support queue does not double;
- p95 decision latency stays below 250 ms, including the feature lookup;
- the model has a registered version, a recorded run id, and a rollback target.

Promotion is a versioned change: serve `login-risk` by version, keep the rule
path available behind a flag, and start with 10% of traffic. Move to 100% only
after 48 hours with no alert on the promotion metrics.

## Rollback

The owner is the security-analytics on-call engineer. Roll back immediately,
without waiting for a meeting, when any of these holds for 15 minutes:

- precision on the live sample falls below 0.80;
- the block rate rises more than 5 percentage points above the shadow baseline;
- p95 latency exceeds 500 ms;
- the model service returns an error for more than 1% of requests;
- a dependency is unavailable and the model cannot score.

Rollback means routing 100% of traffic back to the module 7 rules, keeping the
decision log, and opening an incident with the model version and run id. If the
model service is down, the rules must still answer; the model is never a
blocking dependency for the allow/mfa/block decision.
