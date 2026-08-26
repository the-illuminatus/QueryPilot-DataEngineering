"""Reads raw incoming files and performs structural (shape-only) validation.

Ingestion only confirms a file is readable and correctly shaped -- that it
exists, is non-empty, and has the expected columns. It never inspects the
values inside those columns; that is the data-quality stage's job, not
ingestion's.
"""

from pathlib import Path

import pandas as pd

from src.ingestion.schemas import EXPECTED_COLUMNS


class IngestionShapeError(Exception):
    """Raised when a raw file fails a structural (not value-level) check."""


def read_raw_file(entity: str, source_path: Path) -> pd.DataFrame:
    if not source_path.exists():
        raise IngestionShapeError(f"{entity}: source file not found at {source_path}")

    try:
        # Read everything as plain strings -- ingestion must not silently
        # coerce or "fix" values (e.g. turning blanks into NaN, or dropping
        # leading zeros from an id). That interpretation belongs to the
        # data-quality stage.
        df = pd.read_csv(source_path, dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError as exc:
        raise IngestionShapeError(f"{entity}: source file has no data ({source_path})") from exc

    if df.empty:
        raise IngestionShapeError(f"{entity}: source file has no rows ({source_path})")

    validate_file_shape(entity, df)
    return df


def validate_file_shape(entity: str, df: pd.DataFrame) -> None:
    expected = EXPECTED_COLUMNS[entity]
    missing = [column for column in expected if column not in df.columns]
    if missing:
        raise IngestionShapeError(
            f"{entity}: missing expected column(s) {missing}; found {list(df.columns)}"
        )
