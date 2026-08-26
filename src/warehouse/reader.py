"""Loads curated Parquet output for a batch, for warehouse loading.

Warehouse loading never re-runs transformation -- it only reads what
Phase 4 already produced under data/curated/batch_id=.../. Path logic is
reused from src.transformation.writer rather than redefined here.
"""

from src.ingestion.schemas import ENTITIES
from src.transformation.writer import curated_entity_path

import pandas as pd


class WarehouseInputError(Exception):
    """Raised when the warehouse loader cannot even begin: the requested
    curated batch doesn't exist, a curated file is missing/corrupt, or
    this batch has already been successfully loaded. A pipeline failure,
    distinct from a database error encountered while loading rows that
    do exist.
    """


def load_curated_batch(batch_id: str) -> dict:
    missing = [entity for entity in ENTITIES if not curated_entity_path(entity, batch_id).exists()]
    if missing:
        raise WarehouseInputError(
            f"Curated batch '{batch_id}' is missing output for entities: {missing}. "
            f"Run `python -m src.transformation.pipeline --batch-id {batch_id}` first."
        )

    data = {}
    for entity in ENTITIES:
        path = curated_entity_path(entity, batch_id)
        try:
            data[entity] = pd.read_parquet(path)
        except Exception as exc:  # pyarrow/pandas raise various error types for corrupt files
            raise WarehouseInputError(f"{entity}: curated Parquet file is corrupt ({path})") from exc
    return data
