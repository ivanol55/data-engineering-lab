"""Shared helpers for modules 2-9.

The checks run inside the lab containers. They talk to the running services
over the Compose network, not by importing the learner's modules, so a check
proves the deployed behaviour rather than a local function.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import trino

ROOT = Path("/workspace")


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 900,
) -> subprocess.CompletedProcess:
    result = subprocess.run(
        command,
        cwd=cwd or ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"--- stdout ---\n{result.stdout[-6000:]}\n"
            f"--- stderr ---\n{result.stderr[-6000:]}"
        )
    return result


def run_python(script: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return run([sys.executable, str(script), *args], env=env)


def connect(catalog: str = "iceberg", schema: str = "marts"):
    return trino.dbapi.connect(
        host="trino",
        port=8080,
        user="lab",
        catalog=catalog,
        schema=schema,
    )


def sql(statement: str, *, catalog: str = "iceberg", schema: str = "marts") -> list[tuple[Any, ...]]:
    connection = connect(catalog=catalog, schema=schema)
    try:
        cursor = connection.cursor()
        cursor.execute(statement)
        return cursor.fetchall()
    finally:
        connection.close()


def scalar(statement: str, *, catalog: str = "iceberg", schema: str = "marts") -> Any:
    rows = sql(statement, catalog=catalog, schema=schema)
    return rows[0][0] if rows else None


def delete_s3_prefix(prefix: str) -> None:
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
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket="lakehouse", Prefix=prefix):
        keys = [{"Key": item["Key"]} for item in page.get("Contents", [])]
        if keys:
            client.delete_objects(Bucket="lakehouse", Delete={"Objects": keys})


def drop_schema(name: str) -> None:
    """Drop every relation and remove its files before dropping the schema.

    Lakekeeper purges data asynchronously. A new table at the same location
    fails with "Unexpected files in location" if the purge has not finished,
    so the check removes the S3 prefix itself after dropping the relation.
    """
    rows = sql(
        "select table_name, table_type from iceberg.information_schema.tables "
        f"where table_schema = '{name}'"
    )
    for table_name, table_type in rows:
        if table_type == "VIEW":
            sql(f'DROP VIEW IF EXISTS iceberg.{name}."{table_name}"')
        else:
            sql(f'DROP TABLE IF EXISTS iceberg.{name}."{table_name}"')
            delete_s3_prefix(f"warehouse/{table_name}/")
    sql(f"DROP SCHEMA IF EXISTS iceberg.{name} CASCADE")


def table_rows(name: str) -> list[dict]:
    import pyiceberg
    from pyiceberg.catalog import load_catalog

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
    return catalog.load_table(name).scan().to_arrow().to_pylist()
