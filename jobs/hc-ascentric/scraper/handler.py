"""
CronJob handler: scrape today's Ascentric portfolio and append one row per
account_type to personal_finance.account_history plus one totals row to
personal_finance.portfolio_total.

Ascentric productName -> dashboard account_type:
    SIPP -> Pension
    ISA  -> ISA
    GIA  -> GIA

Values are summed across all accounts sharing a productName (closed accounts
return 0.0 and contribute nothing).
"""

import json
import os
from datetime import date
from typing import Any

import requests

from scraper import fetch_portfolio_data


ICEBERG_WRITER_URL = os.environ.get(
    "ICEBERG_WRITER_URL",
    "http://iceberg-writer.iceberg.svc.cluster.local",
).rstrip("/")
ICEBERG_WRITER_TOKEN = os.environ["ICEBERG_WRITER_TOKEN"]

NAMESPACE     = "personal_finance"
HISTORY_TABLE = "account_history"
TOTAL_TABLE   = "portfolio_total"

ACCOUNT_TYPE_MAP = {
    "SIPP": "Pension",
    "ISA":  "ISA",
    "GIA":  "GIA",
}

# Ascentric account statusCode values. 1 = active, 3 = closed. Closed
# accounts return zero balances but still appear in the API response.
CLOSED_STATUS_CODE = 3


def handle(event, context):
    try:
        print("Fetching portfolio data from Ascentric...", flush=True)
        payload = fetch_portfolio_data()
        data = payload["data"]

        snapshot_date = date.today().isoformat()
        total_value   = float(data["totalPortfolioValue"])

        by_type: dict[str, float] = {}
        for grp in data.get("accountGroups", []):
            for acc in grp.get("accounts", []):
                if acc.get("statusCode") == CLOSED_STATUS_CODE:
                    continue
                product      = acc.get("productName")
                account_type = ACCOUNT_TYPE_MAP.get(product)
                if account_type is None:
                    print(f"  warning: unknown productName {product!r}, skipping", flush=True)
                    continue
                by_type[account_type] = by_type.get(account_type, 0.0) + float(acc.get("totalValue", 0.0))

        history_rows = [
            {"as_of_date": snapshot_date, "account_type": t, "value": v, "source": "ascentric"}
            for t, v in sorted(by_type.items())
        ]
        total_row = {
            "as_of_date":  snapshot_date,
            "total_value": total_value,
            "source":      "ascentric",
        }

        print(
            f"Snapshot {snapshot_date}: total=£{total_value:,.2f}, "
            f"by_type={by_type}",
            flush=True,
        )

        _post_rows(HISTORY_TABLE, history_rows)
        _post_rows(TOTAL_TABLE,   [total_row])

        return {
            "statusCode": 200,
            "body": json.dumps({
                "status":      "ok",
                "total_value": total_value,
                "by_type":     by_type,
            }),
        }

    except Exception as exc:
        print(f"ERROR: {exc}", flush=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(exc)}),
        }


def _post_rows(table: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        print(f"No rows for {NAMESPACE}.{table}, skipping.", flush=True)
        return
    url = f"{ICEBERG_WRITER_URL}/write/{NAMESPACE}/{table}"
    response = requests.post(
        url,
        json={"rows": rows},
        headers={
            "Authorization": f"Bearer {ICEBERG_WRITER_TOKEN}",
            "Content-Type":  "application/json",
        },
        timeout=60,
    )
    response.raise_for_status()
    print(f"Wrote {len(rows)} row(s) to {NAMESPACE}.{table}", flush=True)
