"""Loads a completed ingestion batch for validation.

Validation only ever *reads* an existing raw batch -- it never creates,
mutates, or overwrites anything under data/raw/<entity>/batch_id=.../.

`config.settings` is imported as a module (not `from ... import
DATA_RAW_DIR`) so tests can monkeypatch `settings.DATA_RAW_DIR`.
"""

from pathlib import Path

import pandas as pd

from config import settings
from src.ingestion.schemas import ENTITIES, EXPECTED_COLUMNS


class ValidationInputError(Exception):
    """Raised when the pipeline cannot even begin validating: the batch (or
    an entity within it) doesn't exist, a raw file is empty/corrupt, or it
    is missing expected columns. A pipeline failure -- distinct from
    ordinary data-quality rejections found while validating rows that do
    exist.
    """


def batch_entity_path(entity: str, batch_id: str) -> Path:
    return settings.DATA_RAW_DIR / entity / f"batch_id={batch_id}" / f"{entity}.csv"


def load_batch(batch_id: str) -> dict:
    missing = [entity for entity in ENTITIES if not batch_entity_path(entity, batch_id).exists()]
    if missing:
        raise ValidationInputError(
            f"Batch '{batch_id}' is missing raw data for entities: {missing}"
        )

    data = {}
    for entity in ENTITIES:
        path = batch_entity_path(entity, batch_id)
        try:
            df = pd.read_csv(path, dtype=str, keep_default_na=False)
        except pd.errors.EmptyDataError as exc:
            raise ValidationInputError(f"{entity}: raw file is empty or corrupt ({path})") from exc

        missing_columns = [c for c in EXPECTED_COLUMNS[entity] if c not in df.columns]
        if missing_columns:
            raise ValidationInputError(
                f"{entity}: raw file for batch '{batch_id}' is missing column(s) {missing_columns}"
            )
        if df.empty:
            raise ValidationInputError(f"{entity}: raw file for batch '{batch_id}' has no rows")

        data[entity] = df
    return data
