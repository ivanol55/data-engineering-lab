"""Shared helpers for the module 1 checks."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path("/workspace")
RUN = ROOT / "modules" / "01-batch-ingestion" / "exercises" / "run.py"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "generator") not in sys.path:
    sys.path.insert(0, str(ROOT / "generator"))

from pipelines.ingestion import config  # noqa: E402
from pipelines.ingestion.pipeline import iceberg_catalog  # noqa: E402


def run_pipeline(*commands: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [sys.executable, str(RUN), *commands],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"`run.py {' '.join(commands)}` failed with exit {result.returncode}\n"
            f"--- stdout ---\n{result.stdout[-4000:]}\n"
            f"--- stderr ---\n{result.stderr[-4000:]}"
        )
    return result


def reset() -> None:
    run_pipeline("reset")


def table(name: str):
    return iceberg_catalog().load_table(f"{config.DATASET_NAME}.{name}")


def rows(name: str) -> list[dict]:
    return table(name).scan().to_arrow().to_pylist()


def postgres(statement: str, params: tuple | None = None) -> None:
    import psycopg

    with psycopg.connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(statement, params)
        connection.commit()


def fixture_event_files() -> list[Path]:
    return sorted(config.EVENTS_DIR.glob("*.jsonl"))


def count_jsonl(paths: list[Path]) -> int:
    total = 0
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            total += sum(1 for line in handle if line.strip())
    return total


def expected_threat_intel() -> dict[tuple[str, str], dict]:
    """Latest revision per (indicator, valid_from), read straight from fixtures."""
    latest: dict[tuple[str, str], dict] = {}
    for path in sorted(config.THREAT_INTEL_DIR.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                key = (row["indicator"], str(row["valid_from"]))
                current = latest.get(key)
                if current is None or str(row["updated_at"]) >= str(current["updated_at"]):
                    latest[key] = row
    return latest
