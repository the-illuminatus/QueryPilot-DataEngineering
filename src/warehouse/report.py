"""Builds and writes the machine-readable warehouse load report for a batch.

Unlike prior phases' report locations, this one has no accompanying data
files of its own -- the actual loaded data lives in PostgreSQL, not on
disk -- so data/warehouse/batch_id=.../ holds only this JSON report.
"""

import json
from pathlib import Path
from typing import Optional

from config import settings


def warehouse_batch_dir(batch_id: str) -> Path:
    return settings.DATA_WAREHOUSE_DIR / f"batch_id={batch_id}"


def report_path(batch_id: str) -> Path:
    return warehouse_batch_dir(batch_id) / "load_report.json"


def build_load_report(
    batch_id: str,
    status: str,
    started_at: str,
    completed_at: str,
    duration_seconds: float,
    entity_results: dict,
    quality_checks: dict,
    warnings: list,
    error: Optional[str] = None,
) -> dict:
    total_rows = sum(r.get("loaded", 0) for r in entity_results.values())
    return {
        "batch_id": batch_id,
        "status": status,
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_seconds": duration_seconds,
        "entities": entity_results,
        "total_rows": total_rows,
        "quality_checks": quality_checks,
        "warnings": warnings,
        "error": error,
    }


def write_load_report(batch_id: str, report: dict) -> Path:
    path = report_path(batch_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))
    return path
