"""
OpenFaaS function handler: ascentric-scraper

Triggered by the OpenFaaS cron-connector on a schedule.
Fetches portfolio data from the Ascentric portal, transforms it into
flat row dicts, and POSTs to the generic slate-iceberg-writer service.
"""

import json
import os
import requests
from scraper import fetch_portfolio_data


ICEBERG_WRITER_BASE  = os.environ.get(
    "ICEBERG_WRITER_BASE",
    "http://slate-iceberg-writer.slate-data.svc.cluster.local",
)
ICEBERG_WRITER_TOKEN = os.environ["ICEBERG_WRITER_TOKEN"]


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {ICEBERG_WRITER_TOKEN}",
        "Content-Type":  "application/json",
    }


def _post(path: str, rows: list[dict]) -> dict:
    url = f"{ICEBERG_WRITER_BASE}{path}"
    response = requests.post(
        url,
        json={"rows": rows},
        headers=_headers(),
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def _build_summary_row(data: dict) -> dict:
    return {
        "total_portfolio_value": data["totalPortfolioValue"],
        "total_portfolio_asset": data["totalPortfolioAsset"],
        "total_portfolio_cash":  data["totalPortfolioCash"],
        "total_available_cash":  data["totalAvailableCash"],
    }


def _build_account_rows(data: dict) -> list[dict]:
    rows = []
    for group in data["accountGroups"]:
        for account in group["accounts"]:
            rows.append({
                "account_id":         account["id"],
                "account_number":     account["accountNumber"],
                "product_name":       account["productName"],
                "product_type":       account["productTypeName"],
                "group_name":         group["groupName"],
                "designation":        account.get("accountDesignation"),
                "model_name":         account.get("modelName"),
                "asset_value":        account["assetValue"],
                "portfolio_cash":     account["portfolioCash"],
                "available_cash":     account["availableCash"],
                "total_value":        account["totalValue"],
                "status_code":        account["statusCode"],
                "is_linked_to_model": account["isLinkedToModel"],
            })
    return rows


def handle(event, context):
    try:
        print("Fetching portfolio data from Ascentric...", flush=True)
        payload = fetch_portfolio_data()
        data    = payload["data"]

        total = data["totalPortfolioValue"]
        print(f"Fetched snapshot: total value = £{total:,.2f}", flush=True)

        # Write summary (one row)
        summary_result = _post(
            "/write/personal_finance/portfolio_summary",
            [_build_summary_row(data)],
        )
        print(f"Summary written: {summary_result}", flush=True)

        # Write per-account rows
        account_rows   = _build_account_rows(data)
        accounts_result = _post(
            "/write/personal_finance/account_snapshots",
            account_rows,
        )
        print(f"Accounts written: {accounts_result}", flush=True)

        return {
            "statusCode": 200,
            "body": json.dumps({
                "status":            "ok",
                "total_value":       total,
                "accounts_written":  accounts_result["rows_written"],
            }),
        }

    except Exception as exc:
        print(f"ERROR: {exc}", flush=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(exc)}),
        }
