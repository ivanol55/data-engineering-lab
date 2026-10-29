"""Lab exporter for module 8.

Prometheus cannot query Iceberg or Kafka by itself. This small process turns
the questions the dashboards ask into gauges:

* how many rows are in each table, and how old is the newest event;
* how far behind is each Kafka consumer group;
* are any Debezium connector tasks failing.

It is deliberately boring and small. The learner changes the alert thresholds
and the dashboard, not the exporter.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone

import requests
from confluent_kafka import Consumer
from confluent_kafka.admin import AdminClient
from prometheus_client import Gauge, start_http_server
from pyiceberg.catalog import load_catalog

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("lab-exporter")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
KAFKA_CONNECT_URL = os.getenv("KAFKA_CONNECT_URL", "http://kafka-connect:8083")
PORT = int(os.getenv("EXPORTER_PORT", "9101"))
INTERVAL = int(os.getenv("EXPORTER_INTERVAL_SECONDS", "15"))

TABLES = (
    "raw.users",
    "raw.login_events",
    "raw.threat_intel",
    "marts.fct_login_events",
    "marts.dim_users",
)

LAB_TABLE_ROWS = Gauge("lab_table_row_count", "Rows in a lakehouse table.", ["table"])
LAB_TABLE_MAX_EVENT = Gauge(
    "lab_table_max_event_time_seconds",
    "Newest event_time in a table, as a Unix timestamp.",
    ["table"],
)
LAB_KAFKA_LAG = Gauge(
    "lab_kafka_consumer_lag",
    "Consumer lag per group, topic and partition.",
    ["group", "topic", "partition"],
)
LAB_CONNECTOR_FAILED = Gauge(
    "lab_connector_failed_tasks",
    "Number of non-RUNNING tasks for a Debezium connector.",
    ["connector"],
)
LAB_EXPORTER_SUCCESS = Gauge(
    "lab_exporter_last_success_timestamp_seconds",
    "When the exporter last completed a collection cycle.",
)
LAB_EXPORTER_ERRORS = Gauge(
    "lab_exporter_collection_errors_total",
    "Collection cycles that raised an exception.",
)


def catalog():
    return load_catalog(
        "lakekeeper",
        type="rest",
        uri=f"{os.getenv('LAKEKEEPER_URL', 'http://lakekeeper:8181')}/catalog",
        warehouse=os.getenv("LAKEKEEPER_WAREHOUSE", "lakehouse"),
        token="dummy",
        **{
            "s3.endpoint": os.getenv("S3_ENDPOINT", "http://seaweedfs:8333"),
            "s3.access-key-id": os.getenv("S3_ACCESS_KEY", "labadmin"),
            "s3.secret-access-key": os.getenv("S3_SECRET_KEY", "labadmin123"),
            "s3.region": os.getenv("S3_REGION", "us-east-1"),
        },
    )


def collect_tables() -> None:
    cat = catalog()
    for name in TABLES:
        try:
            table = cat.load_table(name)
            arrow = table.scan().to_arrow()
        except Exception as exc:  # noqa: BLE001 - a missing table is normal early
            log.info("table %s not ready: %s", name, exc)
            continue
        LAB_TABLE_ROWS.labels(table=name).set(arrow.num_rows)
        if "event_time" in arrow.column_names and arrow.num_rows:
            values = [
                value
                for value in arrow.column("event_time").to_pylist()
                if value is not None
            ]
            if values:
                newest = max(values)
                if newest.tzinfo is None:
                    newest = newest.replace(tzinfo=timezone.utc)
                LAB_TABLE_MAX_EVENT.labels(table=name).set(newest.timestamp())


def collect_lag() -> None:
    admin = AdminClient({"bootstrap.servers": KAFKA_BOOTSTRAP})
    consumer = Consumer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP,
            "group.id": "lab-exporter-watermarks",
            "enable.auto.commit": False,
        }
    )
    try:
        groups = admin.list_consumer_groups().result().valid
        for group in groups:
            try:
                offsets = admin.list_consumer_group_offsets(group.group_id).result()
            except Exception as exc:  # noqa: BLE001
                log.info("offsets for %s not ready: %s", group.group_id, exc)
                continue
            for tp, committed in offsets.items():
                try:
                    low, high = consumer.get_watermark_offsets(tp, timeout=2, cached=False)
                except Exception:  # noqa: BLE001
                    continue
                position = committed.offset if committed.offset >= 0 else low
                lag = max(0, high - position)
                LAB_KAFKA_LAG.labels(
                    group=group.group_id,
                    topic=tp.topic,
                    partition=str(tp.partition),
                ).set(lag)
    finally:
        consumer.close()


def collect_connectors() -> None:
    try:
        response = requests.get(
            f"{KAFKA_CONNECT_URL}/connectors?expand=status", timeout=3
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # noqa: BLE001 - Connect is optional in some modules
        log.info("connect not ready: %s", exc)
        return
    for name, info in payload.items():
        tasks = info.get("status", {}).get("tasks", [])
        failed = sum(1 for task in tasks if task.get("state") != "RUNNING")
        LAB_CONNECTOR_FAILED.labels(connector=name).set(failed)


def loop() -> None:
    while True:
        try:
            collect_tables()
            collect_lag()
            collect_connectors()
            LAB_EXPORTER_SUCCESS.set(time.time())
        except Exception as exc:  # noqa: BLE001
            LAB_EXPORTER_ERRORS.inc()
            log.warning("collection cycle failed: %s", exc)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    start_http_server(PORT)
    log.info("exporter listening on :%s", PORT)
    threading.Thread(target=loop, daemon=True).start()
    while True:
        time.sleep(3600)
