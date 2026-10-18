"""
Bulk-import bank/credit-card CSVs from .dev/samples/<account>/*.csv into
personal_finance.transactions.

Idempotent: each row's transaction_id is a deterministic hash of
(bank, account, date, amount, description); re-running on the same files
produces the same IDs, so iceberg-writer / Trino can dedupe at query time
or you can wipe and re-load freely.

Usage (from the repo root with port-forward, OR via kubectl exec):

    ICEBERG_WRITER_URL=http://localhost:8000 \\
    ICEBERG_WRITER_TOKEN=<token>             \\
    python hc-banking/scripts/bulk_import.py

Add --dry-run to just print row counts per source without posting.
"""

import argparse
import glob
import os
import sys

import requests

from parsers import (
    parse_amex,
    parse_hsbc_current,
    parse_lloyds_current,
    parse_starling,
)


NAMESPACE  = "personal_finance"
TABLE      = "transactions"
BATCH_SIZE = 500


SOURCES = [
    {
        "bank":         "lloyds",
        "account_name": "Lloyds Current",
        "account_type": "current",
        "source_tag":   "csv_lloyds_current",
        "parser":       parse_lloyds_current,
        "glob":         "hc-banking/.dev/samples/lloyds-current/*.csv",
    },
    {
        "bank":         "starling",
        "account_name": "Starling Current",
        "account_type": "current",
        "source_tag":   "csv_starling",
        "parser":       parse_starling,
        "glob":         "hc-banking/.dev/samples/starling/*.csv",
    },
    {
        "bank":         "amex",
        "account_name": "Amex Card",
        "account_type": "credit_card",
        "source_tag":   "csv_amex",
        "parser":       parse_amex,
        "glob":         "hc-banking/.dev/samples/amex/*.csv",
    },
    {
        "bank":         "hsbc",
        "account_name": "HSBC Current",
        "account_type": "current",
        "source_tag":   "csv_hsbc_current",
        "parser":       parse_hsbc_current,
        "glob":         "hc-banking/.dev/samples/hsbc-current/*.csv",
    },
]


def collect_rows() -> list[dict]:
    seen: set[str] = set()
    out:  list[dict] = []
    for src in SOURCES:
        n_files = 0
        n_kept  = 0
        n_dup   = 0
        for path in sorted(glob.glob(src["glob"])):
            n_files += 1
            with open(path, encoding="utf-8-sig") as f:
                for row in src["parser"](f, account_name=src["account_name"]):
                    row["bank"]         = src["bank"]
                    row["account_type"] = src["account_type"]
                    row["source"]       = src["source_tag"]
                    if row["transaction_id"] in seen:
                        n_dup += 1
                        continue
                    seen.add(row["transaction_id"])
                    out.append(row)
                    n_kept += 1
        print(f"  {src['account_name']:20} {n_files} file(s)  {n_kept:5} unique  {n_dup:4} dupes")
    return out


def post_rows(rows: list[dict], base: str, token: str) -> None:
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        r = requests.post(
            f"{base.rstrip('/')}/write/{NAMESPACE}/{TABLE}",
            json={"rows": batch},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type":  "application/json",
            },
            timeout=180,
        )
        if not r.ok:
            raise RuntimeError(f"POST failed: {r.status_code} {r.text[:500]}")
        print(f"  posted {i + len(batch)}/{len(rows)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="parse only; don't POST")
    args = ap.parse_args()

    rows = collect_rows()
    print(f"\nTotal: {len(rows)} unique transactions across all sources")

    if args.dry_run or not rows:
        return 0

    base  = os.environ.get("ICEBERG_WRITER_URL", "http://localhost:8000")
    token = os.environ["ICEBERG_WRITER_TOKEN"]
    post_rows(rows, base, token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
