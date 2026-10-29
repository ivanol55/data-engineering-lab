"""Point-in-time features for the login-risk model.

Every feature for an event is computed from events strictly before it. The
current event's outcome, MFA result and attack label are never inputs: they
are the thing being predicted.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from . import config

ROOT = Path("/workspace")
EVENTS_DIR = ROOT / "fixtures" / "events"

FEATURE_COLUMNS = [
    "prior_events",
    "prior_failures",
    "prior_distinct_ips",
    "prior_distinct_countries",
    "seconds_since_previous",
    "is_new_device",
    "risk_score",
    "hour_of_day",
]


def load_events() -> pd.DataFrame:
    records: list[dict] = []
    for path in sorted(EVENTS_DIR.glob("events-*.jsonl")):
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    if not records:
        raise FileNotFoundError(
            f"no fixture events in {EVENTS_DIR}; run `make fixtures` first"
        )
    frame = pd.DataFrame.from_records(records)
    frame["event_time"] = pd.to_datetime(frame["event_time"], utc=True)
    return frame


def _state() -> dict:
    return {
        "events": 0,
        "failures": 0,
        "ips": set(),
        "countries": set(),
        "devices": set(),
        "last_time": None,
    }


def build_features(events: pd.DataFrame | None = None) -> pd.DataFrame:
    frame = load_events() if events is None else events.copy()
    frame = frame.sort_values(["event_time", "event_id"]).reset_index(drop=True)

    history: dict[str, dict] = {}
    rows: list[dict] = []
    for row in frame.itertuples(index=False):
        state = history.setdefault(row.user_id, _state())
        if state["last_time"] is None:
            seconds = -1.0
        else:
            seconds = (row.event_time - state["last_time"]).total_seconds()

        current_failure = int(row.outcome != "allow")
        leak = current_failure if config.INCLUDE_CURRENT_EVENT else 0
        rows.append(
            {
                "event_id": row.event_id,
                "user_id": row.user_id,
                "event_time": row.event_time,
                "is_attack": int(bool(row.is_attack)),
                "risk_score": float(row.risk_score),
                "hour_of_day": int(row.event_time.hour),
                "prior_events": state["events"],
                "prior_failures": state["failures"] + leak,
                "prior_distinct_ips": len(state["ips"]),
                "prior_distinct_countries": len(state["countries"]),
                "seconds_since_previous": float(seconds),
                "is_new_device": int(row.device_id not in state["devices"]),
            }
        )

        state["events"] += 1
        state["failures"] += current_failure
        state["ips"].add(row.source_ip)
        state["countries"].add(row.country)
        state["devices"].add(row.device_id)
        state["last_time"] = row.event_time

    return pd.DataFrame(rows)


def split(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (train, test) using the configured split."""
    if config.SPLIT_STRATEGY == "time":
        dates = frame["event_time"].dt.date
        last_day = dates.max()
        cutoff = last_day - pd.Timedelta(days=config.TEST_DAYS - 1)
        train = frame[dates < cutoff]
        test = frame[dates >= cutoff]
    else:
        train, test = train_test_split(
            frame,
            test_size=0.2,
            random_state=config.RANDOM_SEED,
            shuffle=True,
        )
    return (
        train.sort_values("event_time").reset_index(drop=True),
        test.sort_values("event_time").reset_index(drop=True),
    )


def dataset() -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = build_features()
    return split(frame)


def features_for_request(
    *,
    user_id: str,
    event_time: str,
    source_ip: str,
    country: str,
    device_id: str,
    risk_score: float,
) -> pd.DataFrame:
    """Build the same feature row for one request from prior history.

    The current event is not in the history, so the serving path cannot use
    the leaked ``prior_failures`` value even if training did.
    """
    moment = pd.Timestamp(event_time)
    if moment.tzinfo is None:
        moment = moment.tz_localize("UTC")
    else:
        moment = moment.tz_convert("UTC")

    events = load_events()
    history = events[
        (events["user_id"] == user_id) & (events["event_time"] < moment)
    ].sort_values("event_time")

    prior_failures = int((history["outcome"] != "allow").sum())
    last_time = history["event_time"].max() if not history.empty else None
    seconds = (
        (moment - last_time).total_seconds() if last_time is not None else -1.0
    )
    return pd.DataFrame(
        [
            {
                "prior_events": len(history),
                "prior_failures": prior_failures,
                "prior_distinct_ips": int(history["source_ip"].nunique()),
                "prior_distinct_countries": int(history["country"].nunique()),
                "seconds_since_previous": float(seconds),
                "is_new_device": int(device_id not in set(history["device_id"])),
                "risk_score": float(risk_score),
                "hour_of_day": int(moment.hour),
            }
        ]
    )[FEATURE_COLUMNS]
