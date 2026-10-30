"""Module 0 checks: the environment and the written model of it."""

from __future__ import annotations

import re
from pathlib import Path

import psycopg
import requests
from psycopg.rows import dict_row
from pyiceberg.catalog import load_catalog

ROOT = Path("/workspace")
ANSWERS = ROOT / "modules" / "00-environment" / "answers.md"

QUESTIONS = 8
MIN_ANSWER_CHARS = 120

REQUIRED_TERMS = {
    1: ("postgres", "lakekeeper", "iceberg"),
    2: ("snapshot", "schema", "partition"),
    3: ("kafka", "replay"),
    4: ("at-least-once", "primary key"),
    5: ("partition", "prun"),
    6: ("single", "production"),
    7: ("docker", "ram"),
    8: ("check", "fail"),
}


def _postgres_scalar(sql: str):
    with psycopg.connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            return cursor.fetchone()[0]


def test_postgres_seed_is_complete():
    assert _postgres_scalar("SELECT count(*) FROM users") == 2000
    assert _postgres_scalar("SELECT count(*) FROM roles") == 5
    assert _postgres_scalar("SELECT count(*) FROM users WHERE deleted_at IS NOT NULL") == 42
    statuses = set(
        row["account_status"]
        for row in _rows("SELECT DISTINCT account_status FROM users")
    )
    assert statuses == {"active", "disabled", "locked", "suspended"}


def test_trino_is_healthy_and_reads_postgres():
    response = requests.get("http://trino:8080/v1/info", timeout=10)
    response.raise_for_status()
    assert response.json()["starting"] is False

    import trino

    connection = trino.dbapi.connect(
        host="trino", port=8080, user="lab", catalog="postgresql", schema="public"
    )
    cursor = connection.cursor()
    cursor.execute("SELECT count(*) FROM users")
    assert cursor.fetchone()[0] == 2000


def test_lakekeeper_and_iceberg_namespace():
    response = requests.get("http://lakekeeper:8181/health", timeout=10)
    response.raise_for_status()

    catalog = load_catalog(
        "lakekeeper",
        type="rest",
        uri="http://lakekeeper:8181/catalog",
        warehouse="lakehouse",
        token="dummy",
        **{
            "s3.endpoint": "http://seaweedfs:8333",
            "s3.access-key-id": "labadmin",
            "s3.secret-access-key": "labadmin123",
            "s3.region": "us-east-1",
        },
    )
    namespaces = {
        namespace[0] if isinstance(namespace, tuple) else namespace
        for namespace in catalog.list_namespaces()
    }
    assert "raw" in namespaces, f"raw namespace missing; found {sorted(namespaces)}"


def test_seaweedfs_bucket_exists():
    import boto3
    from botocore.config import Config

    client = boto3.client(
        "s3",
        endpoint_url="http://seaweedfs:8333",
        aws_access_key_id="labadmin",
        aws_secret_access_key="labadmin123",
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )
    buckets = {item["Name"] for item in client.list_buckets()["Buckets"]}
    assert "lakehouse" in buckets


def test_tooling_versions_are_pinned():
    import dlt
    import duckdb
    import pyiceberg

    assert dlt.__version__ == "1.31.0"
    assert pyiceberg.__version__ == "0.12.0"
    assert duckdb.__version__.startswith("2.")


def test_fixtures_are_deterministic_and_non_empty():
    files = sorted((ROOT / "fixtures" / "events").glob("*.jsonl"))
    assert len(files) == 7, f"expected 7 daily event files, found {len(files)}"
    import json

    ids: set[str] = set()
    count = 0
    for path in files:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                event = json.loads(line)
                ids.add(event["event_id"])
                count += 1
    assert count == 14_000
    assert len(ids) == count, "fixture event ids are not unique"


def test_answers_are_filled_in():
    assert ANSWERS.exists(), f"missing {ANSWERS}"
    text = ANSWERS.read_text(encoding="utf-8")
    assert "TODO(learner)" not in text, "answers.md still contains TODO placeholders"

    sections = _sections(text)
    assert set(sections) == set(range(1, QUESTIONS + 1)), (
        f"answers.md must contain Q1..Q{QUESTIONS}; found {sorted(sections)}"
    )
    for number, section in sections.items():
        marker = "### Your answer"
        assert marker in section, (
            f"Q{number} has no {marker!r} section; put your answer below the "
            "question guidance"
        )
        answer = section.split(marker, 1)[1].strip()
        assert len(answer) >= MIN_ANSWER_CHARS, (
            f"Q{number} is too short; explain the trade-off, not just the name"
        )
        lowered = answer.lower()
        missing = [term for term in REQUIRED_TERMS[number] if term not in lowered]
        assert not missing, f"Q{number} is missing these ideas: {missing}"


def _rows(sql: str) -> list[dict]:
    with psycopg.connect() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(sql)
            return cursor.fetchall()


def _sections(text: str) -> dict[int, str]:
    pattern = re.compile(r"^##\s*Q(\d+)\s*$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    sections: dict[int, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[int(match.group(1))] = text[start:end]
    return sections
