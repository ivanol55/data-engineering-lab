"""Module 6 learner decisions.

The job starts with the wrong values; it just computes windows over wall-clock
time, keeps state forever, and has no recovery point. Change one value, cancel
the job, resubmit it, and run ``make check M=6``.
"""

INPUT_TOPIC = "login.events.json"
OUTPUT_TOPIC = "risk.signals"
BOOTSTRAP = "kafka:9092"
JOB_NAME = "risk-signals"
WINDOW_MINUTES = 5

# TODO(learner): "processing" makes the result depend on when the job ran.
# Use "event" so the 2026-09 fixtures produce 2026-09 windows.
TIME_CHARACTERISTIC = "event"

# TODO(learner): the generator can deliver an event slightly out of order.
# Five seconds is the observed bound for this feed.
WATERMARK_SECONDS = 5

# TODO(learner): zero silently drops every event that arrives after its
# window. Ten seconds keeps the generator's late events.
ALLOWED_LATENESS_SECONDS = 10

# TODO(learner): keyed state with no TTL grows forever. A day matches the
# feature's usefulness for this lab.
STATE_TTL_HOURS = 24

# TODO(learner): without checkpoints a TaskManager restart loses state and
# the job cannot recover. Turn this on.
CHECKPOINTING = True
CHECKPOINT_DIR = "file:///opt/flink/checkpoints"
CHECKPOINT_INTERVAL_MS = 5000
