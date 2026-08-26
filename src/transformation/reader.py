"""Loads the already-validated (accepted) rows of a batch for transformation.

Transformation never re-runs Phase 3's validation rules -- it only reads
the accepted-row output validation already produced under
data/validated/batch_id=.../.
"""

import pandas as pd

from src.ingestion.schemas import ENTITIES, EXPECTED_COLUMNS
from src.validation.accepted import accepted_entity_path


class TransformationInputError(Exception):
    """Raised when transformation cannot even begin: the batch hasn't been
    validated yet (no accepted-row output exists), an accepted-row file is
    corrupt or missing expected columns, or curated output already exists
    for this batch. A pipeline failure, distinct from a business
    reconciliation mismatch found while transforming rows that do exist.
    """


def load_accepted_batch(batch_id: str) -> dict:
    missing = [entity for entity in ENTITIES if not accepted_entity_path(entity, batch_id).exists()]
    if missing:
        raise TransformationInputError(
            f"Batch '{batch_id}' has no accepted-row output for entities: {missing}. "
            f"Run `python -m src.validation.pipeline --batch-id {batch_id}` first."
        )

    data = {}
    for entity in ENTITIES:
        path = accepted_entity_path(entity, batch_id)
        try:
            df = pd.read_csv(path, dtype=str, keep_default_na=False)
        except pd.errors.EmptyDataError as exc:
            raise TransformationInputError(
                f"{entity}: accepted-row file is empty/corrupt ({path})"
            ) from exc

        missing_columns = [c for c in EXPECTED_COLUMNS[entity] if c not in df.columns]
        if missing_columns:
            raise TransformationInputError(
                f"{entity}: accepted-row file for batch '{batch_id}' is missing column(s) {missing_columns}"
            )
        data[entity] = df
    return data
