"""Module 1 ingestion entry point.

Usage:
    python exercises/run.py all
    python exercises/run.py users
    python exercises/run.py events
    python exercises/run.py events --date 2026-09-03
    python exercises/run.py threat-intel
    python exercises/run.py reset
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for extra in (ROOT, ROOT / "generator"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from pipelines.ingestion.pipeline import reset_tables, run  # noqa: E402

COMMANDS = {
    "all": ["users", "events", "threat-intel"],
    "users": ["users"],
    "events": ["events"],
    "threat-intel": ["threat-intel"],
    "reset": [],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=sorted(COMMANDS))
    parser.add_argument(
        "--date",
        help="events only: load just this event date (YYYY-MM-DD)",
    )
    args = parser.parse_args()

    if args.command == "reset":
        reset_tables()
        return 0
    if args.date and args.command not in ("events", "all"):
        parser.error("--date is only valid for `events` or `all`")
    run(COMMANDS[args.command], event_date=args.date)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
