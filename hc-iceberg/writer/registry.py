"""
Schema registry for slate-iceberg-writer.

Known tables have explicit PyArrow schemas defined here.
Unknown tables fall back to schema inference from the first row of data.

To register a new table:
    1. Define a pa.Schema in a new module alongside this file
    2. Import and add it to REGISTRY below

The key is a (namespace, table) tuple matching the POST /write/{namespace}/{table} path.
"""

import pyarrow as pa
from personal_finance import (
    ACCOUNT_HISTORY_SCHEMA,
    PORTFOLIO_TOTAL_SCHEMA,
    TRANSACTIONS_SCHEMA,
    LOAN_BALANCES_SCHEMA,
)


# (namespace, table) --> pa.Schema
REGISTRY: dict[tuple[str, str], pa.Schema] = {
    ("personal_finance", "account_history"): ACCOUNT_HISTORY_SCHEMA,
    ("personal_finance", "portfolio_total"): PORTFOLIO_TOTAL_SCHEMA,
    ("personal_finance", "transactions"):    TRANSACTIONS_SCHEMA,
    ("personal_finance", "loan_balances"):   LOAN_BALANCES_SCHEMA,
}


def lookup(namespace: str, table: str) -> pa.Schema | None:
    """Return the registered schema, or None if the table is unknown."""
    return REGISTRY.get((namespace, table))
