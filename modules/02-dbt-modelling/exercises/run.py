"""Module 2 runner.

Usage:
    python exercises/run.py build
    python exercises/run.py build --full-refresh
    python exercises/run.py run
    python exercises/run.py test
    python exercises/run.py debug
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))

import config  # noqa: E402


def dbt_vars() -> dict[str, object]:
    return {
        "fct_incremental_strategy": config.FCT_INCREMENTAL_STRATEGY,
        "fct_unique_key": config.FCT_UNIQUE_KEY,
        "intel_join_mode": config.INTEL_JOIN_MODE,
        "fct_late_window_days": config.FCT_LATE_WINDOW_DAYS,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["build", "run", "test", "debug", "seed"],
        default="build",
        nargs="?",
    )
    parser.add_argument("--full-refresh", action="store_true")
    args = parser.parse_args()

    command = ["dbt", args.command]
    command += [
        "--project-dir",
        str(ROOT / "dbt"),
        "--profiles-dir",
        str(ROOT / "dbt"),
    ]
    if args.command != "debug":
        command += ["--vars", json.dumps(dbt_vars())]
    if args.full_refresh:
        command.append("--full-refresh")

    result = subprocess.run(command, cwd=ROOT)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
