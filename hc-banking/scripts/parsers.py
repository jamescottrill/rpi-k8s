"""
Per-bank CSV row parsers. Each yields dicts in the shape iceberg-writer
expects for personal_finance.transactions, *except* the per-source fields
(`bank`, `account_type`, `source`) which the caller fills in.

Amount sign convention in the yielded dicts: **negative = outflow**.
Amex's CSV uses positive=charge so this module negates Amex amounts.
"""

import csv
import hashlib
from datetime import date, datetime
from typing import IO, Iterable


def _parse_uk_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%d/%m/%Y").date()


def _clean_amount(s: str) -> float:
    s = (s or "").strip().replace(",", "").replace('"', "")
    return float(s) if s else 0.0


def _hash_id(bank: str, account: str, d: date, amount: float, description: str) -> str:
    h = hashlib.sha256()
    h.update(f"{bank}|{account}|{d.isoformat()}|{amount:.2f}|{description.strip()}".encode())
    return h.hexdigest()[:24]


def parse_lloyds_current(file: IO, account_name: str) -> Iterable[dict]:
    """Lloyds personal current account CSV.
    Columns: Transaction Date, Transaction Type, Sort Code, Account Number,
             Transaction Description, Debit Amount, Credit Amount, Balance.
    Sort Code is prefixed with a single-quote to force Excel text-mode; we strip it.
    """
    reader = csv.DictReader(file)
    for row in reader:
        d       = _parse_uk_date(row["Transaction Date"])
        debit   = _clean_amount(row.get("Debit Amount"))
        credit  = _clean_amount(row.get("Credit Amount"))
        amount  = credit - debit
        desc    = (row.get("Transaction Description") or "").strip()
        balance = _clean_amount(row.get("Balance"))
        yield {
            "transaction_id":   _hash_id("lloyds", account_name, d, amount, desc),
            "transaction_date": d.isoformat(),
            "posted_date":      None,
            "amount":           amount,
            "currency":         "GBP",
            "description":      desc,
            "merchant_name":    None,
            "category":         None,
            "account_name":     account_name,
            "running_balance":  balance,
            "transaction_type": (row.get("Transaction Type") or "").strip() or None,
            "reference":        None,
        }


def parse_starling(file: IO, account_name: str) -> Iterable[dict]:
    """Starling personal current account CSV.
    Columns: Date, Counter Party, Reference, Type, Amount (GBP), Balance (GBP),
             Spending Category, Notes.
    Amount is already signed (negative = outflow).
    """
    reader = csv.DictReader(file)
    for row in reader:
        d       = _parse_uk_date(row["Date"])
        amount  = _clean_amount(row.get("Amount (GBP)"))
        cp      = (row.get("Counter Party") or "").strip()
        ref     = (row.get("Reference") or "").strip()
        desc    = cp or ref
        balance = _clean_amount(row.get("Balance (GBP)"))
        yield {
            "transaction_id":   _hash_id("starling", account_name, d, amount, f"{desc}|{ref}"),
            "transaction_date": d.isoformat(),
            "posted_date":      None,
            "amount":           amount,
            "currency":         "GBP",
            "description":      desc,
            "merchant_name":    cp or None,
            "category":         (row.get("Spending Category") or "").strip() or None,
            "account_name":     account_name,
            "running_balance":  balance,
            "transaction_type": (row.get("Type") or "").strip() or None,
            "reference":        ref or None,
        }


def parse_amex(file: IO, account_name: str) -> Iterable[dict]:
    """Amex card statement CSV.
    Columns: Date, Description, Amount.
    Amount is the change in the card balance: positive = charge (you owe more),
    negative = payment received (you owe less).
    """
    reader = csv.DictReader(file)
    for row in reader:
        d        = _parse_uk_date(row["Date"])
        amount   = _clean_amount(row.get("Amount"))
        desc     = (row.get("Description") or "").strip()
        yield {
            "transaction_id":   _hash_id("amex", account_name, d, amount, desc),
            "transaction_date": d.isoformat(),
            "posted_date":      None,
            "amount":           amount,
            "currency":         "GBP",
            "description":      desc,
            "merchant_name":    None,
            "category":         None,
            "account_name":     account_name,
            "running_balance":  None,
            "transaction_type": None,
            "reference":        None,
        }


def parse_hsbc_current(file: IO, account_name: str) -> Iterable[dict]:
    """HSBC current account CSV.
    No header row. Three columns: date, description, amount.
    Amount is already signed (negative = outflow).
    """
    reader = csv.reader(file)
    for row in reader:
        if len(row) < 3 or not row[0].strip():
            continue
        d      = _parse_uk_date(row[0])
        desc   = row[1].strip()
        amount = _clean_amount(row[2])
        yield {
            "transaction_id":   _hash_id("hsbc", account_name, d, amount, desc),
            "transaction_date": d.isoformat(),
            "posted_date":      None,
            "amount":           amount,
            "currency":         "GBP",
            "description":      desc,
            "merchant_name":    None,
            "category":         None,
            "account_name":     account_name,
            "running_balance":  None,
            "transaction_type": None,
            "reference":        None,
        }
