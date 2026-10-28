"""Dagster definitions placeholder (module 3).

The asset below is intentionally small: it proves the webserver, the daemon,
the Postgres-backed instance storage, and the code location all work. Module 3
replaces it with assets for the ingestion, dbt, and streaming jobs.
"""

from __future__ import annotations

import json
from pathlib import Path

from dagster import Definitions, asset

ROOT = Path("/workspace")


@asset(group_name="module_03", compute_kind="python")
def fixture_inventory() -> dict[str, int]:
    """Count the deterministic fixtures the batch path depends on."""
    events = sorted((ROOT / "fixtures" / "events").glob("*.jsonl"))
    intel = sorted((ROOT / "fixtures" / "threat_intel").glob("*.jsonl"))
    events_rows = sum(1 for path in events for _ in path.open(encoding="utf-8"))
    intel_rows = sum(1 for path in intel for _ in path.open(encoding="utf-8"))
    return {"event_files": len(events), "event_rows": events_rows,
            "intel_files": len(intel), "intel_rows": intel_rows}


defs = Definitions(assets=[fixture_inventory])
