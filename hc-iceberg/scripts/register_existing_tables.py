"""
One-off: register the tables that already exist in MinIO with Nessie.

Before this runs, MinIO holds parquet + metadata files written under the old
SQLite catalogue. Nessie is empty. PyIceberg's `register_table` lets us
point Nessie at each table's latest metadata file without rewriting any data.

For each (namespace, table) we:
  1. List <namespace>.db/<table>/metadata/ in MinIO
  2. Pick the highest-numbered NNNNN-*.metadata.json (that's the head)
  3. Ensure the namespace exists in Nessie
  4. catalog.register_table(identifier, metadata_location)

Idempotent: re-running won't duplicate (Nessie rejects existing tables).
"""

import os
import re
import sys
from typing import Any

import boto3
from pyiceberg.catalog import load_catalog
from pyiceberg.exceptions import NamespaceAlreadyExistsError, TableAlreadyExistsError


TABLES = [
    ("personal_finance", "portfolio_summary"),
    ("personal_finance", "account_snapshots"),
    ("personal_finance", "account_history"),
    ("personal_finance", "portfolio_total"),
]


METADATA_RE = re.compile(r"(\d+)-[0-9a-f-]+\.metadata\.json$")


def latest_metadata_key(s3, bucket: str, namespace: str, table: str) -> str | None:
    """Return the S3 key of the highest-numbered metadata.json for a table."""
    prefix = f"{namespace}.db/{table}/metadata/"
    resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    candidates: list[tuple[int, str]] = []
    for obj in resp.get("Contents", []):
        m = METADATA_RE.search(obj["Key"])
        if m:
            candidates.append((int(m.group(1)), obj["Key"]))
    if not candidates:
        return None
    candidates.sort()
    return candidates[-1][1]


def main() -> int:
    bucket = os.environ["S3_BUCKET"]
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
    )

    catalog = load_catalog(
        "nessie",
        **{
            "type":      "rest",
            "uri":       os.environ["NESSIE_URI"],
            "warehouse": os.environ.get("NESSIE_WAREHOUSE", "iceberg"),
            "s3.endpoint":           os.environ["S3_ENDPOINT"],
            "s3.access-key-id":      os.environ["S3_ACCESS_KEY"],
            "s3.secret-access-key":  os.environ["S3_SECRET_KEY"],
            "s3.path-style-access":  "true",
        },
    )

    namespaces = {ns for ns, _ in TABLES}
    for ns in namespaces:
        try:
            catalog.create_namespace(ns)
            print(f"created namespace: {ns}")
        except NamespaceAlreadyExistsError:
            print(f"namespace exists: {ns}")

    for ns, tbl in TABLES:
        key = latest_metadata_key(s3, bucket, ns, tbl)
        if key is None:
            print(f"skip {ns}.{tbl}: no metadata files in MinIO")
            continue
        location = f"s3://{bucket}/{key}"
        try:
            catalog.register_table((ns, tbl), location)
            print(f"registered {ns}.{tbl} -> {location}")
        except TableAlreadyExistsError:
            print(f"already registered {ns}.{tbl}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
