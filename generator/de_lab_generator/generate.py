"""Deterministic login-event and threat-intel generation.

The generator is intentionally boring: a fixed seed, a fixed start date and the
same flags always produce byte-identical fixtures. Event ids are derived from
(seed, UTC date, per-day sequence), so regenerating a single day does not
collide with days generated earlier.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Iterable, Iterator

from .model import (
    ATTACK_NET,
    ATTACK_TYPES,
    AUTH_METHODS,
    BROWSERS,
    DEVICE_TYPES,
    GENERATOR_VERSION,
    NORMAL_NET,
    OPERATING_SYSTEMS,
    TRAVEL_NET,
    device_id,
    event_id,
    session_id,
)
from .users import COUNTRIES, CITIES, LATITUDES, LONGITUDES, USER_COUNT, USERS

UTC = timezone.utc


@dataclass(frozen=True)
class Campaign:
    day_index: int
    index: int
    attack_type: str
    user_index: int
    source_ip: str
    start: datetime
    count: int

    @property
    def attack_id(self) -> str:
        return f"atk-{self.start.date().isoformat()}-{self.index}"


def _rng(seed: int, day: date, purpose: str) -> random.Random:
    return random.Random(f"{seed}:{day.isoformat()}:{purpose}")


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _user(index: int):
    return USERS[index % USER_COUNT]


def _travel_geo(user, rng: random.Random) -> tuple[str, str, float, float]:
    choices = [
        i for i in range(len(COUNTRIES)) if COUNTRIES[i] != user.home_country
    ]
    geo = rng.choice(choices)
    return COUNTRIES[geo], CITIES[geo], LATITUDES[geo], LONGITUDES[geo]


def _normal_ip(user) -> str:
    return f"{NORMAL_NET}.{(user.index % 254) + 1}"


def _travel_ip(user) -> str:
    return f"{TRAVEL_NET}.{(user.index % 200) + 1}"


def _attack_ip(day: date, campaign_index: int) -> str:
    # Keyed on the date, not the batch position, so a one-day regeneration
    # produces the same addresses as the original backfill.
    return f"{ATTACK_NET}.{((day.toordinal() * 31 + campaign_index * 47) % 250) + 1}"


def _device(user, slot: int) -> tuple[str, str, str, str]:
    kind = DEVICE_TYPES[(user.index + slot) % len(DEVICE_TYPES)]
    os_name = OPERATING_SYSTEMS[kind][(user.index + slot) % len(OPERATING_SYSTEMS[kind])]
    browser = BROWSERS[(user.index + slot) % len(BROWSERS)]
    return device_id(user.user_id, slot), kind, os_name, browser


def plan_campaigns(
    seed: int, day: date, day_index: int, attack_count: int
) -> list[Campaign]:
    """Plan attack bursts for one day.

    Planning uses its own RNG stream so it can be replayed when building the
    threat-intel feed without generating the day's normal events.
    """
    rng = _rng(seed, day, "campaigns")
    # Rotation is keyed on the absolute date, not the position in this batch,
    # so generating 2026-09-03 alone produces the same plan as a 7-day backfill.
    count = 2 + (day.toordinal() % 2)
    if attack_count <= 0:
        return []
    count = min(count, attack_count)
    per = attack_count // count
    remainder = attack_count % count
    campaigns: list[Campaign] = []
    for index in range(count):
        attack_type = ATTACK_TYPES[(day.toordinal() * 2 + index) % len(ATTACK_TYPES)]
        # Prefer users that can actually authenticate; disabled users would
        # make every attack look like a blocked login.
        active = [u for u in USERS if u.active]
        user = rng.choice(active)
        minute = 30 + rng.randrange(0, 1380)
        start = _day_start(day) + timedelta(minutes=minute)
        campaigns.append(
            Campaign(
                day_index=day_index,
                index=index,
                attack_type=attack_type,
                user_index=user.index,
                source_ip=_attack_ip(day, index),
                start=start,
                count=per + (1 if index < remainder else 0),
            )
        )
    return campaigns


def _base_event(
    *,
    seq: int,
    day: date,
    when: datetime,
    user,
    ip: str,
    geo: tuple[str, str, float, float],
    device_slot: int,
    outcome: str,
    risk: int,
    mfa_used: bool,
    failure_reason: str | None,
    is_attack: bool,
    attack_type: str | None,
    attack_id: str | None,
    rng: random.Random,
) -> dict:
    country, city, lat, lon = geo
    dev_id, kind, os_name, browser = _device(user, device_slot)
    return {
        "event_id": None,  # assigned after the day is sorted
        "event_time": _iso(when),
        "user_id": user.user_id,
        "email": user.email,
        "session_id": session_id(1337, user.user_id, day.isoformat()),
        "source_ip": ip,
        "country": country,
        "city": city,
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "device_id": dev_id,
        "device_type": kind,
        "operating_system": os_name,
        "browser": browser,
        "auth_method": rng.choice(AUTH_METHODS),
        "mfa_used": mfa_used,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "risk_score": max(0, min(100, risk)),
        "is_attack": is_attack,
        "attack_type": attack_type,
        "attack_id": attack_id,
        "generator_version": GENERATOR_VERSION,
    }


def _normal_event(day: date, seq: int, rng: random.Random) -> dict:
    user = _user(rng.randrange(1, USER_COUNT + 1))
    travel = rng.random() < 0.04
    new_device = rng.random() < 0.015
    geo = _travel_geo(user, rng) if travel else (
        user.home_country,
        user.home_city,
        user.home_lat,
        user.home_lon,
    )
    offset = int(rng.random() * 86_399)
    when = _day_start(day) + timedelta(seconds=offset)
    ip = _travel_ip(user) if travel else _normal_ip(user)

    roll = rng.random()
    if not user.active:
        outcome = "block"
        reason = "account_disabled"
    elif roll < 0.04:
        outcome = "block"
        reason = "bad_password"
    elif roll < 0.12:
        outcome = "mfa_challenge"
        reason = None
    else:
        outcome = "allow"
        reason = None

    risk = rng.randrange(2, 25)
    if travel:
        risk += rng.randrange(20, 30)
    if new_device:
        risk += rng.randrange(10, 25)
    if outcome == "block":
        risk += rng.randrange(5, 20)
    mfa_used = user.mfa_enabled and outcome in ("allow", "mfa_challenge") and rng.random() < 0.7

    return _base_event(
        seq=seq,
        day=day,
        when=when,
        user=user,
        ip=ip,
        geo=geo,
        device_slot=2 + rng.randrange(3) if new_device else 0,
        outcome=outcome,
        risk=risk,
        mfa_used=mfa_used,
        failure_reason=reason,
        is_attack=False,
        attack_type=None,
        attack_id=None,
        rng=rng,
    )


def _campaign_events(campaign: Campaign, day: date, seed: int) -> list[dict]:
    rng = _rng(seed, day, f"attack:{campaign.index}")
    user = _user(campaign.user_index)
    geo = (user.home_country, user.home_city, user.home_lat, user.home_lon)
    events: list[dict] = []
    spacing = max(5, 600 // max(1, campaign.count))

    for i in range(campaign.count):
        when = campaign.start + timedelta(seconds=i * spacing + rng.randrange(0, 20))
        attack_type = campaign.attack_type
        outcome = "block"
        reason = "bad_password"
        risk = 70 + rng.randrange(0, 20)
        mfa_used = False
        device_slot = 0
        event_geo = geo
        ip = campaign.source_ip

        if attack_type == "credential_stuffing":
            user = _user(rng.randrange(1, USER_COUNT + 1))
            geo = (user.home_country, user.home_city, user.home_lat, user.home_lon)
            event_geo = geo
            risk = 75 + rng.randrange(0, 25)
            if rng.random() < 0.08:
                outcome, reason = "allow", None
        elif attack_type == "brute_force":
            user = _user(campaign.user_index)
            risk = 85 + rng.randrange(0, 15)
            if i == campaign.count - 1 and rng.random() < 0.25:
                outcome, reason = "allow", None
        elif attack_type == "impossible_travel":
            home_geo = (user.home_country, user.home_city, user.home_lat, user.home_lon)
            far_geo = _travel_geo(user, rng)
            event_geo = home_geo if i % 2 == 0 else far_geo
            ip = _normal_ip(user) if i % 2 == 0 else _travel_ip(user)
            outcome = "mfa_challenge" if i % 2 else "allow"
            reason = None
            mfa_used = True
            risk = 70 + rng.randrange(0, 25)
            when = campaign.start + timedelta(minutes=8 * i)
        elif attack_type == "mfa_fatigue":
            user = _user(campaign.user_index)
            outcome = "allow" if i == campaign.count - 1 else "mfa_challenge"
            reason = None
            mfa_used = True
            risk = 65 + rng.randrange(0, 25)
            when = campaign.start + timedelta(seconds=i * 45)
        elif attack_type == "account_takeover":
            user = _user(campaign.user_index)
            event_geo = _travel_geo(user, rng)
            device_slot = 4
            ip = f"{TRAVEL_NET}.{200 + (campaign.index % 50)}"
            if i >= campaign.count * 3 // 4:
                outcome, reason = "allow", None
                risk = 95
            else:
                risk = 80 + rng.randrange(0, 15)
            mfa_used = outcome == "allow"
        elif attack_type == "new_device":
            user = _user(campaign.user_index)
            event_geo = _travel_geo(user, rng)
            device_slot = 5
            outcome, reason = "allow", None
            mfa_used = user.mfa_enabled
            risk = 55 + rng.randrange(0, 20)
            when = campaign.start + timedelta(minutes=3 * i)

        events.append(
            _base_event(
                seq=0,  # renumbered by the caller
                day=day,
                when=when,
                user=user,
                ip=ip,
                geo=event_geo,
                device_slot=device_slot,
                outcome=outcome,
                risk=risk,
                mfa_used=mfa_used,
                failure_reason=reason,
                is_attack=True,
                attack_type=attack_type,
                attack_id=campaign.attack_id,
                rng=rng,
            )
        )
    return events


def events_for_day(seed: int, day: date, day_index: int, events_per_day: int, attack_mix: float) -> list[dict]:
    attack_count = max(0, min(events_per_day, round(events_per_day * attack_mix)))
    normal_count = events_per_day - attack_count
    campaigns = plan_campaigns(seed, day, day_index, attack_count)
    events: list[dict] = []
    for campaign in campaigns:
        events.extend(_campaign_events(campaign, day, seed))

    normal_rng = _rng(seed, day, "normal")
    for _ in range(normal_count):
        events.append(_normal_event(day, 0, normal_rng))

    events.sort(
        key=lambda e: (
            e["event_time"],
            e["user_id"],
            e["source_ip"],
            e["outcome"],
            e["attack_id"] or "",
        )
    )
    for seq, event in enumerate(events):
        event["event_id"] = event_id(seed, day.isoformat(), seq)
    return events


def iter_events(
    seed: int,
    start: date,
    days: int,
    events_per_day: int,
    attack_mix: float,
) -> Iterator[dict]:
    for day_index in range(days):
        day = start + timedelta(days=day_index)
        yield from events_for_day(seed, day, day_index, events_per_day, attack_mix)


SEVERITY = {
    "credential_stuffing": "high",
    "brute_force": "high",
    "account_takeover": "critical",
    "mfa_fatigue": "medium",
    "impossible_travel": "medium",
    "new_device": "low",
}
THREAT_TYPE = {
    "new_device": "suspicious_login",
    "impossible_travel": "impossible_travel",
}


def threat_intel_for_day(seed: int, day: date, day_index: int, attack_mix: float, events_per_day: int) -> list[dict]:
    attack_count = max(0, min(events_per_day, round(events_per_day * attack_mix)))
    campaigns = plan_campaigns(seed, day, day_index, attack_count)
    rows: list[dict] = []
    valid_to = day + timedelta(days=3)
    updated = _day_start(day) + timedelta(hours=6)
    for campaign in campaigns:
        rows.append(
            {
                "indicator": campaign.source_ip,
                "indicator_type": "ip",
                "threat_type": THREAT_TYPE.get(campaign.attack_type, campaign.attack_type),
                "confidence": 70 + ((day.toordinal() * 7 + campaign.index * 11) % 25),
                "severity": SEVERITY.get(campaign.attack_type, "medium"),
                "source": "lab-fixture",
                "description": f"Observed {campaign.attack_type} sources in lab traffic",
                "valid_from": day.isoformat(),
                "valid_to": valid_to.isoformat(),
                "updated_at": _iso(updated),
                "generator_version": GENERATOR_VERSION,
            }
        )

    # One low-confidence decoy per day keeps the join honest: matching an
    # indicator is not the same thing as a confirmed attack.
    rows.append(
        {
            "indicator": f"{TRAVEL_NET}.254",
            "indicator_type": "ip",
            "threat_type": "scanner",
            "confidence": 25,
            "severity": "low",
            "source": "lab-fixture",
            "description": "Low-confidence scanner; expect false positives",
            "valid_from": day.isoformat(),
            "valid_to": valid_to.isoformat(),
            "updated_at": _iso(updated),
            "generator_version": GENERATOR_VERSION,
        }
    )

    # Revise two indicators from the previous day. Same natural key
    # (indicator, valid_from), newer payload: a merge must replace, an append
    # must not duplicate.
    if day_index > 0:
        previous_day = day - timedelta(days=1)
        previous = plan_campaigns(seed, previous_day, day_index - 1, attack_count)
        for campaign in previous[:2]:
            rows.append(
                {
                    "indicator": campaign.source_ip,
                    "indicator_type": "ip",
                    "threat_type": THREAT_TYPE.get(campaign.attack_type, campaign.attack_type),
                    "confidence": 95,
                    "severity": "high",
                    "source": "lab-fixture",
                    "description": "Confidence raised after second observation",
                    "valid_from": previous_day.isoformat(),
                    "valid_to": (previous_day + timedelta(days=3)).isoformat(),
                    "updated_at": _iso(updated),
                    "generator_version": GENERATOR_VERSION,
                }
            )
    return rows


def _write_jsonl(path: Path, records: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, separators=(",", ":"), sort_keys=True))
            handle.write("\n")
            count += 1
    return count


def write_events(
    seed: int,
    start: date,
    days: int,
    events_per_day: int,
    attack_mix: float,
    out: Path,
) -> list[Path]:
    if out.suffix == ".jsonl":
        count = _write_jsonl(
            out,
            iter_events(seed, start, days, events_per_day, attack_mix),
        )
        print(f"wrote {count} events to {out}")
        return [out]

    written: list[Path] = []
    for day_index in range(days):
        day = start + timedelta(days=day_index)
        path = out / f"events-{day.isoformat()}.jsonl"
        count = _write_jsonl(
            path,
            events_for_day(seed, day, day_index, events_per_day, attack_mix),
        )
        print(f"wrote {count} events to {path}")
        written.append(path)
    return written


def write_threat_intel(
    seed: int,
    start: date,
    days: int,
    events_per_day: int,
    attack_mix: float,
    out: Path,
) -> list[Path]:
    if out.suffix == ".jsonl":
        def all_rows():
            for day_index in range(days):
                day = start + timedelta(days=day_index)
                yield from threat_intel_for_day(seed, day, day_index, attack_mix, events_per_day)

        count = _write_jsonl(out, all_rows())
        print(f"wrote {count} threat-intel rows to {out}")
        return [out]

    written: list[Path] = []
    for day_index in range(days):
        day = start + timedelta(days=day_index)
        path = out / f"threat-intel-{day.isoformat()}.jsonl"
        rows = threat_intel_for_day(seed, day, day_index, attack_mix, events_per_day)
        count = _write_jsonl(path, rows)
        print(f"wrote {count} threat-intel rows to {path}")
        written.append(path)
    return written
