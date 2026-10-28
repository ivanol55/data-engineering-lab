"""Pipeline construction, execution and local reset helpers."""

from __future__ import annotations

import shutil
from pathlib import Path

import dlt
from pyiceberg.catalog import load_catalog
from pyiceberg.exceptions import NoSuchTableError

from . import config
from .sources import RESOURCES


def make_pipeline() -> dlt.Pipeline:
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    return dlt.pipeline(
        pipeline_name=config.PIPELINE_NAME,
        pipelines_dir=str(config.STATE_DIR),
        destination=dlt.destinations.filesystem(
            bucket_url=config.S3_BUCKET_URL,
            credentials={
                "aws_access_key_id": config.S3_ACCESS_KEY,
                "aws_secret_access_key": config.S3_SECRET_KEY,
                "region_name": config.S3_REGION,
                "endpoint_url": config.S3_ENDPOINT,
            },
        ),
        dataset_name=config.DATASET_NAME,
    )


def iceberg_catalog():
    return load_catalog(
        "lakekeeper",
        type="rest",
        uri=f"{config.LAKEKEEPER_URL}/catalog",
        warehouse=config.LAKEKEEPER_WAREHOUSE,
        token="dummy",  # ignored: Lakekeeper authz is allow-all in this lab
        **{
            "s3.endpoint": config.S3_ENDPOINT,
            "s3.access-key-id": config.S3_ACCESS_KEY,
            "s3.secret-access-key": config.S3_SECRET_KEY,
            "s3.region": config.S3_REGION,
        },
    )


def reset_tables() -> None:
    catalog = iceberg_catalog()
    for table in ("users", "login_events", "threat_intel"):
        try:
            catalog.drop_table(f"{config.DATASET_NAME}.{table}")
            print(f"dropped {config.DATASET_NAME}.{table}")
        except NoSuchTableError:
            pass
    # dlt stores pipeline state in the destination as well as locally. Remove
    # the dataset prefix so the next run starts from an empty lakehouse.
    import boto3
    from botocore.config import Config

    client = boto3.client(
        "s3",
        endpoint_url=config.S3_ENDPOINT,
        aws_access_key_id=config.S3_ACCESS_KEY,
        aws_secret_access_key=config.S3_SECRET_KEY,
        region_name=config.S3_REGION,
        config=Config(s3={"addressing_style": "path"}),
    )
    bucket = config.S3_BUCKET_URL.split("/")[2]
    prefix = "/".join(config.S3_BUCKET_URL.split("/")[3:]) + f"/{config.DATASET_NAME}/"
    paginator = client.get_paginator("list_objects_v2")
    removed = 0
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        keys = [{"Key": item["Key"]} for item in page.get("Contents", [])]
        if keys:
            client.delete_objects(Bucket=bucket, Delete={"Objects": keys})
            removed += len(keys)
    print(f"deleted {removed} objects under s3://{bucket}/{prefix}")
    if config.STATE_DIR.exists():
        shutil.rmtree(config.STATE_DIR)
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    print("cleared dlt state")


def run(names: list[str]) -> dlt.Pipeline:
    unknown = set(names) - set(RESOURCES)
    if unknown:
        raise SystemExit(f"unknown resources: {', '.join(sorted(unknown))}")
    pipeline = make_pipeline()
    resources = [RESOURCES[name]() for name in names]
    info = pipeline.run(resources)
    print(info)
    if not info.has_failed_jobs:
        counts = _table_counts()
        for table, count in counts.items():
            print(f"{config.DATASET_NAME}.{table}: {count} rows")
    return pipeline


def _table_counts() -> dict[str, int]:
    catalog = iceberg_catalog()
    counts: dict[str, int] = {}
    for table in ("users", "login_events", "threat_intel"):
        try:
            iceberg_table = catalog.load_table(f"{config.DATASET_NAME}.{table}")
            counts[table] = len(iceberg_table.scan().to_arrow())
        except NoSuchTableError:
            counts[table] = 0
    return counts
