"""Rejection record model and writer.

A rejected row keeps its full original data plus every rule it violated,
tagged with the entity, batch, and when it was evaluated -- nothing about
a rejected row is thrown away in favor of a single "primary" reason.
"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config import settings


def rejected_batch_dir(batch_id: str) -> Path:
    return settings.DATA_REJECTED_DIR / f"batch_id={batch_id}"


def rejected_entity_path(entity: str, batch_id: str) -> Path:
    return rejected_batch_dir(batch_id) / f"{entity}.csv"


def build_rejected_rows(df: pd.DataFrame, violations: dict, entity: str, batch_id: str) -> list:
    """violations: {row_index: [{"code": str, "message": str}, ...]}"""
    validated_at = datetime.now(timezone.utc).isoformat()
    rejected = []
    for idx, issues in violations.items():
        rejected.append(
            {
                "entity": entity,
                "batch_id": batch_id,
                "validated_at": validated_at,
                "rejection_reason_codes": [issue["code"] for issue in issues],
                "rejection_reasons": [issue["message"] for issue in issues],
                "original_row": df.loc[idx].to_dict(),
            }
        )
    return rejected


def write_rejected_entity(entity: str, batch_id: str, rejected_rows: list) -> Path:
    output_path = rejected_entity_path(entity, batch_id)
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing rejected output: {output_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    records = []
    for item in rejected_rows:
        record = dict(item["original_row"])
        record["_entity"] = item["entity"]
        record["_batch_id"] = item["batch_id"]
        record["_validated_at"] = item["validated_at"]
        record["_rejection_reason_codes"] = ";".join(item["rejection_reason_codes"])
        record["_rejection_reasons"] = " | ".join(item["rejection_reasons"])
        records.append(record)

    pd.DataFrame(records).to_csv(output_path, index=False)
    return output_path
