"""Writes the valid (accepted) rows of a validated batch.

This is the hand-off point to later pipeline stages: transformation reads
this output rather than re-running any validation rule logic itself.
"""

from pathlib import Path

import pandas as pd

from config import settings


def accepted_batch_dir(batch_id: str) -> Path:
    return settings.DATA_VALIDATED_DIR / f"batch_id={batch_id}"


def accepted_entity_path(entity: str, batch_id: str) -> Path:
    return accepted_batch_dir(batch_id) / f"{entity}.csv"


def write_accepted_entity(entity: str, batch_id: str, df: pd.DataFrame, violations: dict) -> Path:
    output_path = accepted_entity_path(entity, batch_id)
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing validated output: {output_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    accepted_df = df.drop(index=list(violations.keys()))
    accepted_df.to_csv(output_path, index=False)
    return output_path
