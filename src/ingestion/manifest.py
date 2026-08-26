"""Writes the per-run ingestion manifest.

One manifest file per batch id, recording what happened to every entity
in that run -- the audit trail for the run.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from config import settings


def manifest_path(batch_id: str) -> Path:
    return settings.DATA_RAW_DIR / "_batches" / f"{batch_id}.json"


def write_batch_manifest(batch_id: str, entity_results: list) -> Path:
    manifest = {
        "batch_id": batch_id,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "entities": entity_results,
    }
    path = manifest_path(batch_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2))
    return path
