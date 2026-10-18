"""
Manually-entered loan balance snapshots → iceberg-writer.

Usage (from inside the iceberg-writer pod, after kubectl cp'ing the yaml):

    ICEBERG_WRITER_URL=http://localhost:8000 \\
    ICEBERG_WRITER_TOKEN=<token>             \\
    python import_loans.py /path/to/loans.yaml

Expected YAML shape:

    - loan_name: NatWest Mortgage
      lender:    NatWest
      loan_type: mortgage
      snapshots:
        - as_of_date: 2024-03-31
          outstanding_balance: 245678.90
          interest_rate: 0.0539
          monthly_payment: 1450.00
          term_remaining_months: 280
        - as_of_date: 2024-04-30
          outstanding_balance: 245100.50
"""

import os
import sys
from datetime import date
from typing import Any

import requests
import yaml


NAMESPACE = "personal_finance"
TABLE     = "loan_balances"


def _iso(d: Any) -> str:
    if isinstance(d, date):
        return d.isoformat()
    return str(d)


def main() -> int:
    path  = sys.argv[1] if len(sys.argv) > 1 else "loans.yaml"
    base  = os.environ.get("ICEBERG_WRITER_URL", "http://localhost:8000").rstrip("/")
    token = os.environ["ICEBERG_WRITER_TOKEN"]

    with open(path) as f:
        loans = yaml.safe_load(f)

    rows: list[dict[str, Any]] = []
    for loan in loans:
        for snap in loan["snapshots"]:
            rows.append({
                "as_of_date":            _iso(snap["as_of_date"]),
                "loan_name":             loan["loan_name"],
                "lender":                loan["lender"],
                "loan_type":             loan["loan_type"],
                "outstanding_balance":   float(snap["outstanding_balance"]),
                "interest_rate":         float(snap["interest_rate"])         if snap.get("interest_rate")         is not None else None,
                "monthly_payment":       float(snap["monthly_payment"])       if snap.get("monthly_payment")       is not None else None,
                "term_remaining_months": int(snap["term_remaining_months"])   if snap.get("term_remaining_months") is not None else None,
                "source":                "manual",
            })

    if not rows:
        print("No snapshots to import.")
        return 0

    response = requests.post(
        f"{base}/write/{NAMESPACE}/{TABLE}",
        json={"rows": rows},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        },
        timeout=60,
    )
    response.raise_for_status()
    print(f"Wrote {len(rows)} snapshot(s) to {NAMESPACE}.{TABLE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
