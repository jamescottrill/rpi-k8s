"""
Generic request/response models for slate-iceberg-writer.

The API is intentionally source-agnostic. Callers POST rows of data
to a namespace/table path; the writer handles schema lookup or inference.
"""

from typing import Any
from pydantic import BaseModel, Field


class WriteRequest(BaseModel):
    """
    Generic write request.

    rows: list of dicts, each representing one record.
          Keys must be consistent across all rows in a single request.
          'snapshot_at' is injected automatically -- do not include it.
    """
    rows: list[dict[str, Any]] = Field(..., min_length=1)


class WriteResponse(BaseModel):
    status:       str
    namespace:    str
    table:        str
    rows_written: int
