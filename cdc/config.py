"""Module 5 learner decisions.

The connector still starts with the wrong values; it just misses the snapshot,
misses deletes, or ignores updates. Change one value, run
``python cdc/run.py reset && python cdc/run.py setup``, and run
``make check M=5``.
"""

CONNECTOR_NAME = "users-cdc"
TOPIC_PREFIX = "cdc"
CONNECT_URL = "http://kafka-connect:8083"

# TODO(learner): "no_data" registers the connector but never copies the
# existing 2,000 users. Use "initial" for the first snapshot.
SNAPSHOT_MODE = "no_data"

# TODO(learner): roles change rarely, but a role rename still matters to the
# consumer. Include both tables.
INCLUDE_TABLES = "public.users"

# TODO(learner): a delete event followed by a null tombstone is the contract.
# Keep the tombstone.
EMIT_TOMBSTONES = False

# TODO(learner): a retry after a crash must not insert a second copy, and an
# update must replace the old row. Use an upsert on user_id.
SINK_UPSERT = False

# TODO(learner): if the sink ignores deletes, deleted users stay active.
APPLY_DELETES = False

# Internal names. Changing these requires a fresh slot and a clean sink.
SLOT_NAME = "de_lab_cdc"
PUBLICATION_NAME = "de_lab_cdc_pub"
SCHEMA_HISTORY_TOPIC = "cdc.schema-history"
CONSUMER_GROUP = "cdc-sink"
