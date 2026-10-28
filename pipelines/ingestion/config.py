"""Pipeline settings.

The `TODO(learner)` values below are the module 1 decisions. They are wrong on
purpose: the pipeline runs, but the resulting tables are not trustworthy.
Change a value, re-run `make load`, and re-run `make check M=1`.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(os.getenv("LAB_ROOT", Path(__file__).resolve().parents[2]))
if str(ROOT / "generator") not in sys.path:
    sys.path.insert(0, str(ROOT / "generator"))

from dlt.destinations.impl.filesystem.iceberg_adapter import iceberg_partition  # noqa: E402
from de_lab_generator.model import EVENT_COLUMNS, THREAT_INTEL_COLUMNS  # noqa: E402

PIPELINE_NAME = "ingestion"
DATASET_NAME = "raw"
STATE_DIR = Path(os.getenv("DLT_STATE_DIR", ROOT / "state" / "dlt"))

EVENTS_DIR = Path(os.getenv("EVENTS_DIR", ROOT / "fixtures" / "events"))
THREAT_INTEL_DIR = Path(os.getenv("THREAT_INTEL_DIR", ROOT / "fixtures" / "threat_intel"))

S3_BUCKET_URL = os.getenv("S3_BUCKET_URL", "s3://lakehouse/warehouse")
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://seaweedfs:8333")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "labadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "labadmin123")
S3_REGION = os.getenv("S3_REGION", "us-east-1")

LAKEKEEPER_URL = os.getenv("LAKEKEEPER_URL", "http://lakekeeper:8181")
LAKEKEEPER_WAREHOUSE = os.getenv("LAKEKEEPER_WAREHOUSE", "lakehouse")

# dlt reads the Iceberg catalog through this env var. Building it from the
# same values as the rest of the lab keeps host and container runs aligned.
ICEBERG_CATALOG_CONFIG = {
    "type": "rest",
    "uri": f"{LAKEKEEPER_URL}/catalog",
    "warehouse": LAKEKEEPER_WAREHOUSE,
    "s3.endpoint": S3_ENDPOINT,
    "s3.access-key-id": S3_ACCESS_KEY,
    "s3.secret-access-key": S3_SECRET_KEY,
    "s3.region": S3_REGION,
}
os.environ.setdefault("ICEBERG_CATALOG__ICEBERG_CATALOG_NAME", "lakekeeper")
os.environ.setdefault("ICEBERG_CATALOG__ICEBERG_CATALOG_TYPE", "rest")
os.environ.setdefault(
    "ICEBERG_CATALOG__ICEBERG_CATALOG_CONFIG", json.dumps(ICEBERG_CATALOG_CONFIG)
)

# ---------------------------------------------------------------------------
# Learner decisions. Every TODO below is checked by `make check M=1`.
# ---------------------------------------------------------------------------

# TODO(learner): a snapshot needs a natural key, otherwise a re-run appends a
# second copy of every user.
USERS_PRIMARY_KEY = None
USERS_WRITE_DISPOSITION = "append"

# TODO(learner): decide what happens when `users.deleted_at` becomes non-null.
# Allowed values: "soft_delete", "hard_delete". "TODO" silently keeps deleted
# users as active.
DELETION_POLICY = "TODO"

# TODO(learner): a backfill followed by yesterday's file must not re-load the
# whole history. Enable the cursor on `event_time`.
EVENTS_INCREMENTAL = False

# TODO(learner): partition login events by day. Use
# `iceberg_partition.day("event_time")` on the solutions branch.
EVENTS_PARTITION = None

# TODO(learner): the threat-intel feed revises previous indicators. Without a
# composite key and merge, revisions become duplicate rows.
THREAT_INTEL_PRIMARY_KEY = None
THREAT_INTEL_WRITE_DISPOSITION = "append"

USER_COLUMNS = {
    "user_id": {"data_type": "text", "nullable": False},
    "email": {"data_type": "text"},
    "full_name": {"data_type": "text"},
    "role_id": {"data_type": "bigint"},
    "account_status": {"data_type": "text"},
    "department": {"data_type": "text"},
    "home_country": {"data_type": "text"},
    "home_city": {"data_type": "text"},
    "home_lat": {"data_type": "double"},
    "home_lon": {"data_type": "double"},
    "mfa_enabled": {"data_type": "bool"},
    "created_at": {"data_type": "timestamp", "timezone": True},
    "updated_at": {"data_type": "timestamp", "timezone": True},
    "last_login_at": {"data_type": "timestamp", "timezone": True},
    "deleted_at": {"data_type": "timestamp", "timezone": True},
    "is_deleted": {"data_type": "bool"},
}
