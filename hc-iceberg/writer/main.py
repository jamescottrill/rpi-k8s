"""
slate-iceberg-writer

A lightweight FastAPI service that accepts arbitrary row data and appends
it to Iceberg tables on MinIO. Fully source-agnostic -- the route encodes
the destination, not the origin.

Any OpenFaaS function or service on the cluster can POST here to persist
data without managing its own Iceberg or S3 connection.

Endpoints:
    POST /write/{namespace}/{table}   write rows to any Iceberg table
    GET  /health                      liveness probe
    GET  /tables                      list all known tables across namespaces
"""

import os
from fastapi import FastAPI, HTTPException, Security, Path
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from models import WriteRequest, WriteResponse
from writer import write_rows


app    = FastAPI(title="slate-iceberg-writer", version="2.0.0")
bearer = HTTPBearer()

API_TOKEN = os.environ.get("API_TOKEN", "")


def _verify_token(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    if not API_TOKEN:
        raise HTTPException(status_code=500, detail="API_TOKEN not configured on server")
    if credentials.credentials != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    return credentials


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/write/{namespace}/{table}", response_model=WriteResponse)
def write(
    namespace: str = Path(..., pattern=r"^[a-z][a-z0-9_]*$"),
    table:     str = Path(..., pattern=r"^[a-z][a-z0-9_]*$"),
    body:      WriteRequest = ...,
    credentials: HTTPAuthorizationCredentials = Security(_verify_token),
):
    """
    Write rows to an Iceberg table.

    - Uses a registered schema if (namespace, table) is known.
    - Infers schema from the data for unknown tables.
    - 'snapshot_at' is injected automatically -- do not include it in rows.

    Example:
        POST /write/personal_finance/portfolio_summary
        {
            "rows": [
                {
                    "total_portfolio_value": 347418.78,
                    "total_portfolio_asset": 341634.06,
                    "total_portfolio_cash":  5784.72,
                    "total_available_cash":  5784.72
                }
            ]
        }
    """
    try:
        rows_written = write_rows(namespace, table, body.rows)
        return WriteResponse(
            status="ok",
            namespace=namespace,
            table=table,
            rows_written=rows_written,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
