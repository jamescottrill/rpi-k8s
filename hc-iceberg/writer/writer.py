"""
Core PyIceberg writer -- generic, table-agnostic.

Hybrid schema strategy:
    - Known tables: schema looked up from registry.py
    - Unknown tables: schema inferred from the first row of data

'snapshot_at' (UTC timestamp) is injected automatically into every row.

Migration note: to move to Nessie later, swap the catalogue config in
get_catalogue() and register existing table locations via the Nessie API.
No data files need to move.
"""

import os
from datetime import date, datetime, timezone
from typing import Any

import pyarrow as pa
from pyiceberg.catalog import load_catalog
from pyiceberg.exceptions import NoSuchTableError

from registry import lookup


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------

def get_catalogue():
    """
    Load a PyIceberg REST catalogue pointing at Nessie.

    Nessie holds the table-version pointers; the actual parquet + metadata
    files live in MinIO. Client-side S3 credentials are supplied directly
    so we don't depend on Nessie's credential-vending path.
    """
    return load_catalog(
        "nessie",
        **{
            "type":      "rest",
            "uri":       os.environ["NESSIE_URI"],
            "warehouse": os.environ.get("NESSIE_WAREHOUSE", "iceberg"),
            # Force PyArrowFileIO — Nessie's REST config defaults to Fsspec
            # which PyIceberg 0.8's scan path rejects with a confusing
            # "Expected PyArrowFileIO or FsspecFileIO" type error.
            "py-io-impl": "pyiceberg.io.pyarrow.PyArrowFileIO",
            "s3.endpoint":           os.environ["S3_ENDPOINT"],
            "s3.access-key-id":      os.environ["S3_ACCESS_KEY"],
            "s3.secret-access-key":  os.environ["S3_SECRET_KEY"],
            "s3.path-style-access":  "true",
        },
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_namespace(catalogue, namespace: str) -> None:
    existing = [ns[0] for ns in catalogue.list_namespaces()]
    if namespace not in existing:
        catalogue.create_namespace(namespace)


def _get_or_create_table(catalogue, namespace: str, table: str, schema: pa.Schema):
    full_name = (namespace, table)
    try:
        return catalogue.load_table(full_name)
    except NoSuchTableError:
        # PyIceberg accepts a PyArrow schema directly and assigns field IDs.
        return catalogue.create_table(full_name, schema=schema)


def _infer_schema(rows: list[dict[str, Any]]) -> pa.Schema:
    """
    Infer a PyArrow schema from the first row, then prepend snapshot_at.
    Types default to PyArrow's inference from Python native types.

    Skips any snapshot_at field already present in the sample (it has been
    injected by _inject_snapshot_at upstream) — the explicit field is
    re-added with the canonical timestamp("us", tz="UTC") type.
    """
    sample = pa.Table.from_pylist(rows[:1])
    fields = [pa.field("snapshot_at", pa.timestamp("us", tz="UTC"), nullable=False)]
    for field in sample.schema:
        if field.name == "snapshot_at":
            continue
        fields.append(field)
    return pa.schema(fields)


def _inject_snapshot_at(
    rows: list[dict[str, Any]],
    snapshot_at: datetime,
) -> list[dict[str, Any]]:
    return [{"snapshot_at": snapshot_at, **row} for row in rows]


def _coerce_to_schema(
    rows: list[dict[str, Any]],
    schema: pa.Schema,
) -> list[dict[str, Any]]:
    """
    Apply schema-driven coercions for types PyArrow can't auto-cast from JSON.
    Currently:
      - date32 fields: parse ISO 'YYYY-MM-DD' strings into datetime.date
        (JSON has no date type, so clients send strings).
    """
    date_fields = [f.name for f in schema if pa.types.is_date(f.type)]
    if not date_fields:
        return rows
    out: list[dict[str, Any]] = []
    for row in rows:
        new_row = dict(row)
        for name in date_fields:
            val = new_row.get(name)
            if isinstance(val, str):
                new_row[name] = date.fromisoformat(val)
        out.append(new_row)
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def write_rows(namespace: str, table: str, rows: list[dict[str, Any]]) -> int:
    """
    Write rows to an Iceberg table, creating it if it does not exist.

    Uses a registered schema if one exists for (namespace, table),
    otherwise infers the schema from the data.

    Args:
        namespace: Iceberg namespace (e.g. 'personal_finance').
        table:     Iceberg table name (e.g. 'portfolio_summary').
        rows:      List of row dicts. Must not include 'snapshot_at'.

    Returns:
        Number of rows written.
    """
    snapshot_at = datetime.now(timezone.utc)
    rows        = _inject_snapshot_at(rows, snapshot_at)

    registered_schema = lookup(namespace, table)
    schema            = registered_schema if registered_schema is not None else _infer_schema(rows)

    rows = _coerce_to_schema(rows, schema)

    catalogue = get_catalogue()
    _ensure_namespace(catalogue, namespace)
    iceberg_table = _get_or_create_table(catalogue, namespace, table, schema)

    arrow_table = pa.Table.from_pylist(rows, schema=schema)

    with iceberg_table.transaction() as txn:
        txn.append(arrow_table)

    return len(rows)
