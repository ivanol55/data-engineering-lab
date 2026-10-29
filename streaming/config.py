"""Module 4 learner decisions.

The stream still runs with the values below; it just loses ordering, loses
acknowledgements, or duplicates the sink. Change one value, run
``python streaming/run.py setup && python streaming/run.py produce``, and run
``make check M=4``.
"""

TOPIC = "login.events"
BROKER = "kafka:9092"
SCHEMA_SUBJECT = "login.events-value"
REGISTRY_URL = "http://apicurio:8080/apis/registry/v2"

# TODO(learner): one partition is not a design. The reference is three, which
# gives room for three consumers without changing ordering per user.
PARTITION_COUNT = 1

# TODO(learner): keying by event_id preserves nothing useful. Per-user state
# needs every event for a user on one partition. Use "user_id".
MESSAGE_KEY = None

# TODO(learner): "1" acknowledges only the leader. Use "all".
ACKS = "1"

# TODO(learner): an idempotent producer needs acks=all. Turn this on after
# ACKS is fixed, otherwise the producer will reject the configuration.
ENABLE_IDEMPOTENCE = False

# TODO(learner): auto-commit commits offsets that have not reached the sink.
# Turn it off and commit after the write.
AUTO_COMMIT = True

# TODO(learner): renaming a field is not a compatible change. Use "BACKWARD"
# and let the registry reject it.
SCHEMA_COMPATIBILITY = "NONE"

# TODO(learner): a replay must not duplicate the sink. The reference sink
# deduplicates on event_id.
SINK_IDEMPOTENT = False

CONSUMER_GROUP = "login-events-sink"
SINK_PATH = "/workspace/state/stream-sink.jsonl"
