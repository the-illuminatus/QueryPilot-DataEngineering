"""Batch identifier generation for ingestion runs.

One batch id is created per ingestion run and shared across every entity
processed in that run, so the whole run can be traced and replayed
together.
"""

import uuid
from datetime import datetime, timezone


def create_batch_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid.uuid4().hex[:6]
    return f"{timestamp}_{suffix}"
