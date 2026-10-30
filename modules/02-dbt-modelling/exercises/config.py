"""Module 2 learner decisions.

Change one value, run `python exercises/run.py build`, and run
`make check M=2`. The project still runs with the wrong values; it just
produces a fact table you cannot trust.
"""

# TODO(learner): `append` is not idempotent. A second build adds the same
# events again. Choose "merge" and keep the unique key below.
FCT_INCREMENTAL_STRATEGY = "merge"

# TODO(learner): the key the merge uses. One row per event means event_id.
FCT_UNIQUE_KEY = "event_id"

# TODO(learner): the intel feed revises indicators and can have overlapping
# validity windows. "indicator_only" fans out; choose "latest_valid" to keep
# one current revision per event inside its validity window.
INTEL_JOIN_MODE = "latest_valid"

# TODO(learner): how far back should an incremental build look for late
# events? Zero drops an event that arrives after the cursor. Two days is the
# reference for this feed.
FCT_LATE_WINDOW_DAYS = 2
