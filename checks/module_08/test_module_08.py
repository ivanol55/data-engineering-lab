"""Behavioural checks for module 8.

The checks ask Prometheus what it actually scraped, then read the artefacts
the learner owns: alert rules, the dashboard, the catalogue and the deletion
procedure.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path

import pytest
import requests
import yaml

ROOT = Path("/workspace")
PROMETHEUS = "http://prometheus:9090"
API = "http://api:8000"
ALERTS = ROOT / "compose" / "prometheus" / "alerts.yml"
DASHBOARD = ROOT / "dashboards" / "lab-overview.json"
CATALOGUE = ROOT / "governance" / "catalogue.yml"
DELETION = ROOT / "governance" / "deletion.md"

EXPECTED_TABLES = {
    "raw.users",
    "raw.login_events",
    "raw.threat_intel",
    "marts.fct_login_events",
    "marts.dim_users",
}


def _query(expr: str) -> list[dict]:
    response = requests.get(
        f"{PROMETHEUS}/api/v1/query", params={"query": expr}, timeout=10
    )
    response.raise_for_status()
    payload = response.json()
    assert payload.get("status") == "success", payload
    return payload["data"]["result"]


def _wait_for(predicate, timeout: int = 120, interval: float = 3.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            last = predicate()
            if last:
                return last
        except Exception as exc:  # noqa: BLE001 - retry until the scrape lands
            last = exc
        time.sleep(interval)
    raise AssertionError(f"condition not met within {timeout}s: {last}")


@pytest.fixture(scope="module", autouse=True)
def scraped_metrics():
    def targets_up():
        response = requests.get(
            f"{PROMETHEUS}/api/v1/targets", params={"state": "active"}, timeout=10
        )
        response.raise_for_status()
        active = response.json()["data"]["activeTargets"]
        up = {target["labels"]["job"] for target in active if target["health"] == "up"}
        return up if {"prometheus", "api", "exporter"} <= up else None

    _wait_for(targets_up)
    # Generate at least one decision so the API counter and histogram exist.
    requests.post(
        f"{API}/decide",
        json={
            "user_id": str(uuid.uuid4()),
            "source_ip": "192.0.2.200",
            "country": "Germany",
            "request_id": str(uuid.uuid4()),
        },
        timeout=5,
    )
    _wait_for(lambda: _query("lab_decisions_total"))
    yield


def test_prometheus_scrapes_the_lab_targets():
    response = requests.get(
        f"{PROMETHEUS}/api/v1/targets", params={"state": "active"}, timeout=10
    )
    response.raise_for_status()
    active = response.json()["data"]["activeTargets"]
    up = {target["labels"]["job"] for target in active if target["health"] == "up"}
    assert {"prometheus", "api", "exporter"} <= up, (
        f"Prometheus is not scraping every lab target; up jobs: {sorted(up)}"
    )


def test_exporter_completes_a_collection_cycle():
    result = _query("lab_exporter_last_success_timestamp_seconds")
    assert result, (
        "the exporter never completed a cycle; table freshness and Kafka lag "
        "are invisible"
    )
    value = float(result[0]["value"][1])
    assert value > 0


def test_api_metrics_reach_prometheus():
    decisions = _query("lab_decisions_total")
    latency = _query("lab_decision_latency_seconds_count")
    assert decisions, "Prometheus has no lab_decisions_total series"
    assert latency, "Prometheus has no lab_decision_latency_seconds series"


def _alert_rules() -> dict[str, dict]:
    payload = yaml.safe_load(ALERTS.read_text(encoding="utf-8"))
    rules: dict[str, dict] = {}
    for group in payload.get("groups", []):
        for rule in group.get("rules", []):
            if "alert" in rule:
                rules[rule["alert"]] = rule
    return rules


def test_alert_rules_have_bounded_thresholds_and_a_runbook():
    rules = _alert_rules()
    expected = {
        "RawEventsStale",
        "KafkaConsumerLagHigh",
        "DecisionDependencyErrors",
        "ConnectorTaskFailed",
    }
    missing = expected - set(rules)
    assert not missing, f"the alert file is missing {sorted(missing)}"

    for name, rule in rules.items():
        assert rule.get("for"), f"{name} has no `for:` duration and will flap"
        labels = rule.get("labels", {})
        assert labels.get("severity"), f"{name} has no severity"
        annotations = rule.get("annotations", {})
        runbook = annotations.get("runbook_url", "")
        assert runbook and "TODO" not in runbook, (
            f"{name} has no runbook link; an alert without an action is noise"
        )

    stale = rules["RawEventsStale"]["expr"]
    assert "lab_table_max_event_time_seconds" in stale
    stale_numbers = [int(value) for value in re.findall(r"\d+", stale)]
    assert stale_numbers and min(stale_numbers) <= 7 * 24 * 3600, (
        "RawEventsStale uses a threshold longer than a week"
    )

    lag = rules["KafkaConsumerLagHigh"]["expr"]
    assert "lab_kafka_consumer_lag" in lag
    lag_numbers = [int(value) for value in re.findall(r"\d+", lag)]
    assert lag_numbers and min(lag_numbers) <= 100_000, (
        "KafkaConsumerLagHigh uses an unbounded lag threshold"
    )

    errors = rules["DecisionDependencyErrors"]["expr"]
    assert "lab_dependency_errors_total" in errors
    ratios = [float(value) for value in re.findall(r"0\.\d+", errors)]
    assert ratios and min(ratios) <= 0.5, (
        "DecisionDependencyErrors only fires at an almost total outage"
    )


def test_prometheus_loaded_the_alert_rules():
    response = requests.get(
        f"{PROMETHEUS}/api/v1/rules", params={"type": "alert"}, timeout=10
    )
    response.raise_for_status()
    groups = response.json()["data"]["groups"]
    loaded = {
        rule["name"]
        for group in groups
        for rule in group.get("rules", [])
        if rule.get("type") == "alerting"
    }
    expected = {
        "RawEventsStale",
        "KafkaConsumerLagHigh",
        "DecisionDependencyErrors",
        "ConnectorTaskFailed",
    }
    assert expected <= loaded, (
        f"Prometheus did not load every alert; loaded: {sorted(loaded)}"
    )


def test_dashboard_shows_freshness_lag_and_decisions():
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    exprs = [
        target.get("expr", "")
        for panel in dashboard.get("panels", [])
        for target in panel.get("targets", [])
    ]
    blob = "\n".join(exprs)
    required = {
        "lab_table_max_event_time_seconds",
        "lab_table_row_count",
        "lab_kafka_consumer_lag",
        "lab_decision_latency_seconds_bucket",
        "lab_connector_failed_tasks",
    }
    missing = {metric for metric in required if metric not in blob}
    assert not missing, (
        f"the dashboard does not query {sorted(missing)}; a dashboard that "
        "only shows `up` cannot tell you the data is stale"
    )
    assert len(dashboard.get("panels", [])) >= 5


def test_catalogue_covers_every_table():
    catalogue = yaml.safe_load(CATALOGUE.read_text(encoding="utf-8"))
    tables = catalogue.get("tables") or {}
    missing = EXPECTED_TABLES - set(tables)
    assert not missing, f"the catalogue is missing {sorted(missing)}"

    for name, entry in tables.items():
        assert entry.get("owner") and entry["owner"] != "TODO", (
            f"{name} has no owner; an unowned table has nobody to page"
        )
        assert entry.get("grain"), f"{name} has no declared grain"
        retention = entry.get("retention_days")
        assert isinstance(retention, int) and retention > 0, (
            f"{name} has no positive retention period"
        )
        assert isinstance(entry.get("pii_columns"), list), (
            f"{name} has no PII inventory (use an empty list for none)"
        )
        upstream = entry.get("upstream")
        assert isinstance(upstream, list) and upstream, (
            f"{name} has no upstream dependencies"
        )


def test_deletion_procedure_reaches_every_system():
    text = DELETION.read_text(encoding="utf-8")
    lowered = text.lower()
    for heading in ("## scope", "## procedure", "## verification", "## retention"):
        assert heading in lowered, f"the deletion procedure is missing {heading!r}"
    for system in ("postgres", "iceberg", "kafka", "valkey", "mlflow"):
        assert system in lowered, (
            f"the deletion procedure does not mention {system}; a copy there "
            "survives the request"
        )
    assert "TODO(learner)" not in text, "the deletion procedure is still a placeholder"
