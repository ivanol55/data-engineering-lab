"""Score one login request with the trained model.

Usage:
    python ml/score.py \
      --user-id 00000000-0000-0000-0000-000000000004 \
      --event-time 2026-09-07T12:00:00Z \
      --source-ip 203.0.113.10 \
      --country Germany \
      --device-id dev-1 \
      --risk-score 80
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml import config, features  # noqa: E402


def rule_decision(risk_score: float, prior_failures: int) -> str:
    """A stand-in for the module 7 rules, used for shadow comparison."""
    if risk_score >= 70 or prior_failures >= 3:
        return "block"
    return "allow"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--event-time", required=True)
    parser.add_argument("--source-ip", required=True)
    parser.add_argument("--country", required=True)
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--risk-score", type=float, required=True)
    args = parser.parse_args()

    model_path = Path(config.MODEL_PATH)
    if not model_path.exists():
        raise SystemExit(
            f"{model_path} does not exist; run `python ml/train.py` first"
        )
    with model_path.open("rb") as handle:
        model = pickle.load(handle)

    row = features.features_for_request(
        user_id=args.user_id,
        event_time=args.event_time,
        source_ip=args.source_ip,
        country=args.country,
        device_id=args.device_id,
        risk_score=args.risk_score,
    )
    probability = float(model.predict_proba(row)[0, 1])
    model_decision = "block" if probability >= 0.5 else "allow"
    prior_failures = int(row["prior_failures"].iloc[0])

    result = {
        "model_score": round(probability, 6),
        "model_decision": model_decision,
        "shadow": bool(config.SHADOW_MODE),
        "rule_decision": (
            rule_decision(args.risk_score, prior_failures)
            if config.SHADOW_MODE
            else None
        ),
    }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
