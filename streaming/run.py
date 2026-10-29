"""Module 4 entry point.

Usage:
    python streaming/run.py reset
    python streaming/run.py setup
    python streaming/run.py produce
    python streaming/run.py consume --limit 1000
    python streaming/run.py consume --replay --limit 1000
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from streaming import config  # noqa: E402
from streaming.consumer import consume  # noqa: E402
from streaming.producer import produce  # noqa: E402
from streaming.registry import (  # noqa: E402
    delete_schema,
    register_schema,
    set_compatibility,
)
from streaming.topics import create_topic, delete_topic, describe_topic  # noqa: E402


def reset() -> None:
    delete_topic()
    delete_schema()
    Path(config.SINK_PATH).unlink(missing_ok=True)
    print("deleted topic, schema and sink")


def setup() -> None:
    create_topic()
    register_schema()
    set_compatibility()
    print(f"topic {config.TOPIC}: {describe_topic()}")
    print(
        f"schema {config.SCHEMA_SUBJECT}: compatibility "
        f"{config.SCHEMA_COMPATIBILITY}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["reset", "setup", "produce", "consume"])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--replay", action="store_true")
    args = parser.parse_args()

    if args.command == "reset":
        reset()
    elif args.command == "setup":
        setup()
    elif args.command == "produce":
        print(f"produced {produce(limit=args.limit)} events")
    else:
        print(consume(limit=args.limit, replay=args.replay))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
