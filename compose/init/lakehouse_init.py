#!/usr/bin/env python3
"""One-shot bootstrap for the local lakehouse.

Creates the S3 bucket, bootstraps Lakekeeper, creates the `lakehouse`
warehouse, and creates the `raw` namespace. Idempotent: every step tolerates
the resource already existing. This is plumbing; a failure here is loud.
"""

from __future__ import annotations

import os
import sys
import time

import boto3
import requests
from botocore.config import Config
from botocore.exceptions import ClientError
from pyiceberg.catalog import load_catalog

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://seaweedfs:8333")
S3_BUCKET = os.getenv("S3_BUCKET", "lakehouse")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "labadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "labadmin123")
S3_REGION = os.getenv("S3_REGION", "us-east-1")

LAKEKEEPER_URL = os.getenv("LAKEKEEPER_URL", "http://lakekeeper:8181")
WAREHOUSE = os.getenv("LAKEKEEPER_WAREHOUSE", "lakehouse")
NAMESPACE = os.getenv("LAKEKEEPER_NAMESPACE", "raw")


def wait_for(label: str, fn, attempts: int = 60, delay: float = 1.0) -> None:
    last: Exception | None = None
    for _ in range(attempts):
        try:
            fn()
            return
        except Exception as exc:  # noqa: BLE001 - the message is the point
            last = exc
            time.sleep(delay)
    raise SystemExit(f"{label} did not become ready: {last}")


def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name=S3_REGION,
        config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3}),
    )


def ensure_bucket() -> None:
    client = s3_client()
    try:
        client.head_bucket(Bucket=S3_BUCKET)
        print(f"bucket {S3_BUCKET!r} already exists")
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code not in {"404", "NoSuchBucket", "NotFound"}:
            raise
        client.create_bucket(Bucket=S3_BUCKET)
        print(f"created bucket {S3_BUCKET!r}")


def lakekeeper_ready() -> None:
    response = requests.get(f"{LAKEKEEPER_URL}/health", timeout=3)
    response.raise_for_status()


def bootstrap_lakekeeper() -> None:
    response = requests.post(
        f"{LAKEKEEPER_URL}/management/v1/bootstrap",
        json={"accept-terms-of-use": True, "is-operator": True},
        timeout=10,
    )
    already = (
        response.status_code == 400
        and response.json().get("error", {}).get("type") == "CatalogAlreadyBootstrapped"
    )
    if response.status_code == 409 or already:
        print("Lakekeeper already bootstrapped")
        return
    response.raise_for_status()
    print("bootstrapped Lakekeeper")


def ensure_warehouse() -> None:
    listing = requests.get(
        f"{LAKEKEEPER_URL}/management/v1/warehouse", timeout=10
    )
    listing.raise_for_status()
    if any(w.get("name") == WAREHOUSE for w in listing.json().get("warehouses", [])):
        print(f"warehouse {WAREHOUSE!r} already exists")
        return

    payload = {
        "warehouse-name": WAREHOUSE,
        "storage-credential": {
            "type": "s3",
            "credential-type": "access-key",
            "aws-access-key-id": S3_ACCESS_KEY,
            "aws-secret-access-key": S3_SECRET_KEY,
        },
        "storage-profile": {
            "type": "s3",
            "bucket": S3_BUCKET,
            "region": S3_REGION,
            "endpoint": S3_ENDPOINT,
            "path-style-access": True,
            "flavor": "s3-compat",
            "sts-enabled": False,
            # Static credentials are simpler and more reliable against
            # SeaweedFS than Lakekeeper's remote-signing proxy.
            "remote-signing-enabled": False,
            "key-prefix": "warehouse",
        },
        "delete-profile": {"type": "hard"},
    }
    response = requests.post(
        f"{LAKEKEEPER_URL}/management/v1/warehouse",
        json=payload,
        timeout=30,
    )
    if response.status_code == 409:
        print(f"warehouse {WAREHOUSE!r} already exists")
        return
    if not response.ok:
        raise SystemExit(
            f"warehouse creation failed: {response.status_code} {response.text}"
        )
    print(f"created warehouse {WAREHOUSE!r}")


def ensure_namespace() -> None:
    catalog = load_catalog(
        "lakekeeper",
        type="rest",
        uri=f"{LAKEKEEPER_URL}/catalog",
        warehouse=WAREHOUSE,
        token="dummy",  # ignored when Lakekeeper authz is disabled
        **{
            "s3.endpoint": S3_ENDPOINT,
            "s3.access-key-id": S3_ACCESS_KEY,
            "s3.secret-access-key": S3_SECRET_KEY,
            "s3.region": S3_REGION,
        },
    )
    catalog.create_namespace_if_not_exists(NAMESPACE)
    print(f"namespace {NAMESPACE!r} ready")


def main() -> int:
    wait_for("SeaweedFS S3", lambda: s3_client().list_buckets())
    ensure_bucket()
    wait_for("Lakekeeper", lakekeeper_ready)
    bootstrap_lakekeeper()
    ensure_warehouse()
    ensure_namespace()
    print("lakehouse init complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
