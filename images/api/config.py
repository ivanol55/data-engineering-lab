"""Decision-service settings.

The `TODO(learner)` values are module 7 decisions. The service still starts and
answers requests with them, which is the dangerous part: every response looks
valid.
"""

from __future__ import annotations

import os

VALKEY_URL = os.getenv("VALKEY_URL", "redis://valkey:6379/0")
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
DECISION_TOPIC = os.getenv("DECISION_TOPIC", "login.decisions")
RULE_VERSION = "v1"

# Dependency budget. The total must stay below the caller's timeout.
POSTGRES_TIMEOUT_SECONDS = 1.0
VALKEY_TIMEOUT_SECONDS = 0.5

# Lab-only fault injection. The checks use it to prove the fail mode without
# stopping a container. It is enabled by default in Compose and documented in
# module 7. Never enable it outside a lab.
ALLOW_FAULT_INJECTION = os.getenv("LAB_ALLOW_FAULT_INJECTION", "1") == "1"

# TODO(learner): an unknown user is not a low-risk user. Choose "block".
MISSING_USER_DECISION = "block"

# TODO(learner): a deleted or disabled account must not be allowed. Enable the
# status check.
CHECK_ACCOUNT_STATUS = True

# TODO(learner): a source IP on the current intel list must be blocked. Enable
# the intel lookup.
CHECK_INTEL = True

# TODO(learner): intel entries older than this are stale. Pick a TTL that
# matches the feed cadence (3600 seconds is the reference).
INTEL_TTL_SECONDS = 3600

# TODO(learner): what should happen when Postgres or Valkey is unreachable?
# "block" fails closed; "allow" is the wrong default for a security decision.
FAIL_MODE = "block"

# TODO(learner): decisions must be auditable. Enable the Kafka decision log.
DECISION_LOG_ENABLED = True

# The decision cache makes a retried request idempotent. Keep it short: a
# cached decision is only valid while its inputs are.
DECISION_CACHE_TTL_SECONDS = 300

# How long a per-user "last country" observation is trusted.
LAST_COUNTRY_TTL_SECONDS = 3600
