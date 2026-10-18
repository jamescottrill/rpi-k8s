"""
Registered PyArrow schemas for the personal_finance namespace.

These match the rows the ascentric-scraper POSTs after transforming
the raw Ascentric API response into flat row dicts.

'snapshot_at' is injected by the writer -- do not include it in rows.
"""

import pyarrow as pa


PORTFOLIO_SUMMARY_SCHEMA = pa.schema([
    pa.field("snapshot_at",           pa.timestamp("us", tz="UTC"), nullable=False),
    pa.field("total_portfolio_value", pa.float64(),                 nullable=False),
    pa.field("total_portfolio_asset", pa.float64(),                 nullable=False),
    pa.field("total_portfolio_cash",  pa.float64(),                 nullable=False),
    pa.field("total_available_cash",  pa.float64(),                 nullable=False),
])

ACCOUNT_SNAPSHOTS_SCHEMA = pa.schema([
    pa.field("snapshot_at",        pa.timestamp("us", tz="UTC"), nullable=False),
    pa.field("account_id",         pa.int64(),                   nullable=False),
    pa.field("account_number",     pa.string(),                  nullable=False),
    pa.field("product_name",       pa.string(),                  nullable=False),
    pa.field("product_type",       pa.string(),                  nullable=False),
    pa.field("group_name",         pa.string(),                  nullable=False),
    pa.field("designation",        pa.string(),                  nullable=True),
    pa.field("model_name",         pa.string(),                  nullable=True),
    pa.field("asset_value",        pa.float64(),                 nullable=False),
    pa.field("portfolio_cash",     pa.float64(),                 nullable=False),
    pa.field("available_cash",     pa.float64(),                 nullable=False),
    pa.field("total_value",        pa.float64(),                 nullable=False),
    pa.field("status_code",        pa.int32(),                   nullable=False),
    pa.field("is_linked_to_model", pa.bool_(),                   nullable=False),
])

# Normalised, dashboard-friendly schemas. Populated by the historical backfill
# script and (eventually) by a future ascentric handler that maps the rich
# account_snapshots rows down to (account_type, value) per snapshot.
#
# as_of_date is the date the portfolio was valued; snapshot_at is the
# ingestion timestamp. Keeping these separate lets us re-run the backfill
# without losing the original valuation dates.
ACCOUNT_HISTORY_SCHEMA = pa.schema([
    pa.field("snapshot_at",  pa.timestamp("us", tz="UTC"), nullable=False),
    pa.field("as_of_date",   pa.date32(),                  nullable=False),
    pa.field("account_type", pa.string(),                  nullable=False),
    pa.field("value",        pa.float64(),                 nullable=False),
    pa.field("source",       pa.string(),                  nullable=False),
])

PORTFOLIO_TOTAL_SCHEMA = pa.schema([
    pa.field("snapshot_at", pa.timestamp("us", tz="UTC"), nullable=False),
    pa.field("as_of_date",  pa.date32(),                  nullable=False),
    pa.field("total_value", pa.float64(),                 nullable=False),
    pa.field("source",      pa.string(),                  nullable=False),
])


# Bank/credit-card transactions, normalised across providers.
#
#   amount: signed in account currency. Negative = outflow (debit).
#   transaction_id: stable per-source ID. For sources that don't provide one
#     (most CSV exports), the importer derives a deterministic hash from
#     (bank, account, transaction_date, amount, description).
#   posted_date: differs from transaction_date for credit cards; null when
#     the source doesn't distinguish.
#   source: provenance, e.g. csv_lloyds_2026q2, api_starling, api_gocardless_hsbc.
TRANSACTIONS_SCHEMA = pa.schema([
    pa.field("snapshot_at",      pa.timestamp("us", tz="UTC"), nullable=False),
    pa.field("transaction_id",   pa.string(),                  nullable=False),
    pa.field("transaction_date", pa.date32(),                  nullable=False),
    pa.field("posted_date",      pa.date32(),                  nullable=True),
    pa.field("amount",           pa.float64(),                 nullable=False),
    pa.field("currency",         pa.string(),                  nullable=False),
    pa.field("description",      pa.string(),                  nullable=False),
    pa.field("merchant_name",    pa.string(),                  nullable=True),
    pa.field("category",         pa.string(),                  nullable=True),
    pa.field("bank",             pa.string(),                  nullable=False),
    pa.field("account_name",     pa.string(),                  nullable=False),
    pa.field("account_type",     pa.string(),                  nullable=False),
    pa.field("running_balance",  pa.float64(),                 nullable=True),
    pa.field("transaction_type", pa.string(),                  nullable=True),
    pa.field("reference",        pa.string(),                  nullable=True),
    pa.field("source",           pa.string(),                  nullable=False),
])


# Monthly outstanding-balance snapshots for loans (mortgage, personal loans).
# Most lenders don't expose transactions on the loan itself; the user enters
# these manually from monthly statements.
LOAN_BALANCES_SCHEMA = pa.schema([
    pa.field("snapshot_at",           pa.timestamp("us", tz="UTC"), nullable=False),
    pa.field("as_of_date",            pa.date32(),                  nullable=False),
    pa.field("loan_name",             pa.string(),                  nullable=False),
    pa.field("lender",                pa.string(),                  nullable=False),
    pa.field("loan_type",             pa.string(),                  nullable=False),
    pa.field("outstanding_balance",   pa.float64(),                 nullable=False),
    pa.field("interest_rate",         pa.float64(),                 nullable=True),
    pa.field("monthly_payment",       pa.float64(),                 nullable=True),
    pa.field("term_remaining_months", pa.int32(),                   nullable=True),
    pa.field("source",                pa.string(),                  nullable=False),
])
