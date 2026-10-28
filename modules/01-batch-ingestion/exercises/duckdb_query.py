"""Run a SQL query in DuckDB against the Iceberg REST catalog.

Usage: python duckdb_query.py "SELECT count(*) FROM login_events"
"""

from __future__ import annotations

import os
import sys

import duckdb

EXTENSION_DIR = os.getenv("DUCKDB_EXTENSION_DIRECTORY", "/opt/duckdb-extensions")
LAKEKEEPER_URL = os.getenv("LAKEKEEPER_URL", "http://lakekeeper:8181")
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://seaweedfs:8333")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "labadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "labadmin123")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
WAREHOUSE = os.getenv("LAKEKEEPER_WAREHOUSE", "lakehouse")
DATASET = os.getenv("DLT_DATASET_NAME", "raw")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: duckdb_query.py '<sql>'", file=sys.stderr)
        return 2

    endpoint = S3_ENDPOINT.removeprefix("http://").removeprefix("https://").rstrip("/")
    con = duckdb.connect(config={"extension_directory": EXTENSION_DIR})
    con.execute("LOAD iceberg")
    con.execute("LOAD httpfs")
    # DuckDB's Iceberg attach uses the legacy S3 settings for file reads.
    con.execute(f"SET s3_endpoint='{endpoint}'")
    con.execute(f"SET s3_access_key_id='{S3_ACCESS_KEY}'")
    con.execute(f"SET s3_secret_access_key='{S3_SECRET_KEY}'")
    con.execute(f"SET s3_use_ssl={'true' if S3_ENDPOINT.startswith('https') else 'false'}")
    con.execute("SET s3_url_style='path'")
    con.execute(f"SET s3_region='{S3_REGION}'")
    con.execute(
        f"ATTACH '{WAREHOUSE}' AS lake (TYPE iceberg, "
        f"ENDPOINT '{LAKEKEEPER_URL}/catalog', AUTHORIZATION_TYPE 'none')"
    )
    con.execute(f"USE lake.{DATASET}")

    result = con.execute(sys.argv[1])
    columns = [item[0] for item in result.description]
    print("\t".join(columns))
    for row in result.fetchall():
        print("\t".join("" if value is None else str(value) for value in row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
