"""
One-off backfill of historical portfolio snapshots into Iceberg.

Writes to two new tables under the `personal_finance` namespace:

  account_history     (one row per snapshot per account_type)
     as_of_date      DATE
     account_type    TEXT   (Pension / ISA / GIA)
     value           DOUBLE
     source          TEXT   ("manual" for backfill, "ascentric" for live)

  portfolio_total     (one row per snapshot)
     as_of_date      DATE
     total_value     DOUBLE
     source          TEXT

`snapshot_at` is the iceberg-writer-injected ingestion timestamp; `as_of_date`
is the date the portfolio was valued. Keeping these distinct lets you re-run
the backfill if you ever need to without losing the original valuation dates.

Usage (from inside the iceberg-writer pod, where ICEBERG_WRITER_URL defaults
to localhost):

    ICEBERG_WRITER_TOKEN=<token> python backfill_portfolio_history.py

Or from outside via kubectl port-forward:

    kubectl port-forward -n iceberg svc/iceberg-writer 8000:80 &
    ICEBERG_WRITER_URL=http://localhost:8000 \\
    ICEBERG_WRITER_TOKEN=<token> python backfill_portfolio_history.py
"""

import os
import sys
from datetime import date
from typing import Any

import requests


# ---------------------------------------------------------------------------
# Raw historical data
# Format: each tuple is (date_string, pension, isa, gia)
# Years are carried forward where missing (latest explicit year wins).
# 60,8810 from 5/3/25 corrected to 60,810 per user direction.
# ---------------------------------------------------------------------------

RAW: list[tuple[str, float, float, float]] = [
    ("19/4/23",   46_540, 86_263,  103_690),
    ("31/5",      46_465, 84_837,  101_978),
    ("16/6",      47_043, 85_899,  103_252),
    ("15/8",      47_081, 84_703,  101_815),
    ("29/9",      47_184, 83_748,  100_667),
    ("31/12/23",  50_556, 88_178,  105_992),
    ("27/2/24",   52_306, 89_962,  108_137),
    ("18/4",      52_864, 109_974, 88_984),
    ("28/5",      55_444, 113_856, 91_611),
    ("15/7",      56_670, 115_637, 93_049),
    ("29/8",      56_714, 114_278, 91_956),
    ("15/12",     60_584, 119_923, 96_498),
    ("15/1/25",   60_557, 119_179, 95_900),
    ("5/3",       60_810, 118_300, 95_192),
    ("14/5",      61_140, 139_063, 74_157),
    ("11/7",      63_525, 143_466, 71_471),
    ("23/7",      64_218, 145_233, 72_250),
    ("13/8",      65_710, 147_802, 73_528),
    ("14/9",      67_771, 151_634, 75_433),
    ("3/10",      69_651, 155_060.71, 77_138),
    ("31/10",     72_483, 160_594, 79_880),
    ("07/12",     72_139, 159_057, 79_126),
    ("23/12",     71_947, 158_632, 78_914),
    ("31/1/26",   76_316, 166_712, 82_934),
    ("22/4",      80_353, 173_924, 86_524),
    ("23/5",      82_836, 178_520, 88_812),
]

NAMESPACE = "personal_finance"
HISTORY_TABLE = "account_history"
TOTAL_TABLE   = "portfolio_total"
ACCOUNT_TYPES = ("Pension", "ISA", "GIA")


def parse_dates(raw: list[tuple]) -> list[tuple[date, float, float, float]]:
    """Resolve year-elided dates by carrying forward the latest explicit year."""
    out: list[tuple[date, float, float, float]] = []
    current_year: int | None = None
    for date_str, pension, isa, gia in raw:
        parts = date_str.split("/")
        if len(parts) == 3:
            d, m, y = (int(p) for p in parts)
            current_year = 2000 + y if y < 100 else y
        elif len(parts) == 2:
            if current_year is None:
                raise ValueError(f"Cannot infer year for {date_str!r} (no prior year context)")
            d, m = (int(p) for p in parts)
        else:
            raise ValueError(f"Unparseable date: {date_str!r}")
        out.append((date(current_year, m, d), pension, isa, gia))
    return out


def post(base_url: str, token: str, table: str, rows: list[dict[str, Any]]) -> None:
    url = f"{base_url.rstrip('/')}/write/{NAMESPACE}/{table}"
    resp = requests.post(
        url,
        json={"rows": rows},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        },
        timeout=60,
    )
    if not resp.ok:
        raise RuntimeError(f"POST {url} -> {resp.status_code}: {resp.text}")
    print(f"  wrote {len(rows)} row(s) to {NAMESPACE}.{table}")


def main() -> int:
    base = os.environ.get("ICEBERG_WRITER_URL", "http://localhost:8000")
    token = os.environ.get("ICEBERG_WRITER_TOKEN")
    if not token:
        print("ICEBERG_WRITER_TOKEN env var is required", file=sys.stderr)
        return 1

    snapshots = parse_dates(RAW)
    print(f"Parsed {len(snapshots)} snapshots, "
          f"{snapshots[0][0]} -> {snapshots[-1][0]}")

    for snap_date, pension, isa, gia in snapshots:
        iso = snap_date.isoformat()
        print(f"{iso}:")
        account_rows = [
            {"as_of_date": iso, "account_type": t, "value": float(v), "source": "manual"}
            for t, v in zip(ACCOUNT_TYPES, (pension, isa, gia))
        ]
        total_row = {
            "as_of_date":  iso,
            "total_value": float(pension + isa + gia),
            "source":      "manual",
        }
        post(base, token, HISTORY_TABLE, account_rows)
        post(base, token, TOTAL_TABLE,   [total_row])

    return 0


if __name__ == "__main__":
    sys.exit(main())
