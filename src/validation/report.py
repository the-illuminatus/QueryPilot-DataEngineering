"""Builds and writes the machine-readable data-quality report for a batch."""

import json
from datetime import datetime, timezone
from pathlib import Path

from src.validation.rejection import rejected_batch_dir


def report_path(batch_id: str) -> Path:
    return rejected_batch_dir(batch_id) / "quality_report.json"


def build_quality_report(batch_id: str, entity_results: dict) -> dict:
    """entity_results: {entity: {"total", "valid", "rejected", "reason_counts"}}"""
    total_rows = sum(r["total"] for r in entity_results.values())
    valid_rows = sum(r["valid"] for r in entity_results.values())
    rejected_rows = sum(r["rejected"] for r in entity_results.values())
    quality_percentage = round((valid_rows / total_rows) * 100, 2) if total_rows else 0.0

    combined_reason_counts = {}
    entities_section = {}
    for entity, r in entity_results.items():
        for code, count in r["reason_counts"].items():
            combined_reason_counts[code] = combined_reason_counts.get(code, 0) + count
        entities_section[entity] = {
            "total_rows": r["total"],
            "valid_rows": r["valid"],
            "rejected_rows": r["rejected"],
            "quality_percentage": round((r["valid"] / r["total"]) * 100, 2) if r["total"] else 0.0,
            "rejection_reason_counts": r["reason_counts"],
        }

    return {
        "batch_id": batch_id,
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "rejected_rows": rejected_rows,
        "quality_percentage": quality_percentage,
        "entities": entities_section,
        "rejection_reasons": combined_reason_counts,
    }


def write_quality_report(batch_id: str, report: dict) -> Path:
    path = report_path(batch_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))
    return path
