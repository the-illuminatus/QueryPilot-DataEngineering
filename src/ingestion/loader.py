"""Lands a structurally-validated DataFrame into its immutable raw batch partition.

`config.settings` is imported as a module (not `from ... import DATA_RAW_DIR`)
so tests can monkeypatch `settings.DATA_RAW_DIR` and have it take effect here.
"""

from pathlib import Path

import pandas as pd

from config import settings


def batch_output_path(entity: str, batch_id: str) -> Path:
    return settings.DATA_RAW_DIR / entity / f"batch_id={batch_id}" / f"{entity}.csv"


def land_entity(entity: str, df: pd.DataFrame, batch_id: str) -> Path:
    output_path = batch_output_path(entity, batch_id)
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing batch output: {output_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path
