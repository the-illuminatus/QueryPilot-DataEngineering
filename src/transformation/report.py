"""Builds and writes the machine-readable transformation report for a batch."""

import json
from datetime import datetime, timezone
from pathlib import Path

from src.transformation.writer import curated_batch_dir


def report_path(batch_id: str) -> Path:
    return curated_batch_dir(batch_id) / "transformation_report.json"


def build_transformation_report(
    batch_id: str, entity_results: dict, order_reconciliation: dict, warnings: list
) -> dict:
    return {
        "batch_id": batch_id,
        "transformed_at": datetime.now(timezone.utc).isoformat(),
        "entities": entity_results,
        "order_total_reconciliation": order_reconciliation,
        "warnings": warnings,
    }


def write_transformation_report(batch_id: str, report: dict) -> Path:
    path = report_path(batch_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))
    return path
