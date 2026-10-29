"""Create the JSON topics Flink reads and write the fixture events.

Usage:
    python flink_jobs/setup.py reset
    python flink_jobs/setup.py setup
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flink_jobs import config  # noqa: E402

EVENTS_DIR = ROOT / "fixtures" / "events"


def _admin() -> AdminClient:
    return AdminClient({"bootstrap.servers": config.BOOTSTRAP})


def reset() -> None:
    names = [config.INPUT_TOPIC, config.OUTPUT_TOPIC]
    admin = _admin()
    futures = admin.delete_topics(names)
    for future in futures.values():
        try:
            future.result(timeout=10)
        except Exception:
            pass
    for _ in range(60):
        topics = admin.list_topics(timeout=10).topics
        if not any(name in topics for name in names):
            return
        time.sleep(1)
    raise RuntimeError(f"topics were not deleted: {names}")


def setup() -> None:
    admin = _admin()
    topics = [
        NewTopic(name, num_partitions=3, replication_factor=1)
        for name in (config.INPUT_TOPIC, config.OUTPUT_TOPIC)
    ]
    futures = admin.create_topics(topics)
    for future in futures.values():
        try:
            future.result(timeout=30)
        except Exception as exc:
            if "already exists" not in str(exc).lower():
                raise

    producer = Producer(
        {
            "bootstrap.servers": config.BOOTSTRAP,
            "acks": "all",
            "enable.idempotence": True,
        }
    )
    sent = 0
    for path in sorted(EVENTS_DIR.glob("events-*.jsonl")):
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                # Flink's JSON format reads the SQL timestamp form; the
                # fixtures use RFC 3339 with a trailing Z.
                row["event_time"] = row["event_time"].replace("T", " ").rstrip("Z")
                producer.produce(
                    config.INPUT_TOPIC,
                    key=row["user_id"].encode("utf-8"),
                    value=json.dumps(row).encode("utf-8"),
                )
                producer.poll(0)
                sent += 1
    producer.flush(60)
    print(f"produced {sent} events to {config.INPUT_TOPIC}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["reset", "setup"])
    args = parser.parse_args()
    reset() if args.command == "reset" else setup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
