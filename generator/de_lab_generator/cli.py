"""CLI for the deterministic login-event generator."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

from .generate import (
    events_for_day,
    iter_events,
    threat_intel_for_day,
    write_events,
    write_threat_intel,
)

UTC = timezone.utc


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}") from exc


def _default_seed() -> int:
    return int(os.getenv("GENERATOR_SEED", "1337"))


def _default_start() -> date:
    # A fixed date keeps fixtures reproducible. Override with --start.
    return date.fromisoformat(os.getenv("GENERATOR_START", "2026-09-01"))


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--seed", type=int, default=_default_seed())
    parser.add_argument("--start", type=_date, default=_default_start())
    parser.add_argument(
        "--days",
        type=int,
        default=int(os.getenv("BACKFILL_DAYS", "7")),
        help="number of UTC days to generate (backfill)",
    )
    parser.add_argument(
        "--events-per-day",
        type=int,
        default=int(os.getenv("EVENTS_PER_DAY", "2000")),
    )
    parser.add_argument(
        "--attack-mix",
        type=float,
        default=float(os.getenv("GENERATOR_ATTACK_MIX", "0.08")),
        help="fraction of events that belong to attack campaigns",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="de_lab_generator",
        description="Deterministic login events and daily threat-intel fixtures.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    events = sub.add_parser("events", help="write login events as JSONL")
    _add_common(events)
    events.add_argument("--out", type=Path, default=Path("fixtures/events"))

    intel = sub.add_parser("threat-intel", help="write daily threat-intel JSONL")
    _add_common(intel)
    intel.add_argument("--out", type=Path, default=Path("fixtures/threat_intel"))

    both = sub.add_parser("all", help="events + threat intel")
    _add_common(both)
    both.add_argument("--out", type=Path, default=Path("fixtures"))

    plan = sub.add_parser("plan", help="print the attack campaign plan as JSON")
    _add_common(plan)

    stream = sub.add_parser("stream", help="emit events at a fixed rate")
    stream.add_argument("--seed", type=int, default=_default_seed())
    stream.add_argument("--rate", type=float, default=float(os.getenv("GENERATOR_RATE", "2")))
    stream.add_argument("--attack-mix", type=float, default=float(os.getenv("GENERATOR_ATTACK_MIX", "0.08")))
    stream.add_argument("--duration", type=float, default=0, help="seconds; 0 means forever")
    stream.add_argument("--out", default="-", help="'-' for stdout, otherwise a JSONL file")
    stream.add_argument("--start", type=_date, default=None)
    return parser


def _stream(args) -> int:
    day = args.start or datetime.now(UTC).date()
    events = events_for_day(args.seed, day, 0, max(1, int(args.rate * 86400)), args.attack_mix)
    if not events:
        return 0
    handle = sys.stdout if args.out == "-" else open(args.out, "a", encoding="utf-8")
    started = time.monotonic()
    sent = 0
    try:
        while True:
            if args.duration and time.monotonic() - started >= args.duration:
                break
            event = events[sent % len(events)]
            event = dict(event)
            now = datetime.now(UTC)
            event["event_time"] = now.isoformat().replace("+00:00", "Z")
            event["stream_seq"] = sent
            line = json.dumps(event, separators=(",", ":"), sort_keys=True)
            handle.write(line + "\n")
            handle.flush()
            sent += 1
            time.sleep(1 / args.rate if args.rate > 0 else 0)
    except KeyboardInterrupt:
        pass
    finally:
        if handle is not sys.stdout:
            handle.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "events":
        write_events(args.seed, args.start, args.days, args.events_per_day, args.attack_mix, args.out)
    elif args.command == "threat-intel":
        write_threat_intel(args.seed, args.start, args.days, args.events_per_day, args.attack_mix, args.out)
    elif args.command == "all":
        write_events(
            args.seed, args.start, args.days, args.events_per_day, args.attack_mix, args.out / "events"
        )
        write_threat_intel(
            args.seed,
            args.start,
            args.days,
            args.events_per_day,
            args.attack_mix,
            args.out / "threat_intel",
        )
    elif args.command == "plan":
        from .generate import plan_campaigns

        attack_count = round(args.events_per_day * args.attack_mix)
        payload = []
        for day_index in range(args.days):
            day = date.fromordinal(args.start.toordinal() + day_index)
            for campaign in plan_campaigns(args.seed, day, day_index, attack_count):
                payload.append(
                    {
                        "day": day.isoformat(),
                        "attack_id": campaign.attack_id,
                        "attack_type": campaign.attack_type,
                        "user_index": campaign.user_index,
                        "source_ip": campaign.source_ip,
                        "start": campaign.start.isoformat(),
                        "count": campaign.count,
                    }
                )
        json.dump(payload, sys.stdout, indent=2)
        print()
    elif args.command == "stream":
        return _stream(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
