"""Writes each entity's transformed DataFrame to Parquet via PyArrow.

Batch-partitioned and immutable, mirroring the ingestion/validation
modules' "never overwrite" guarantee. Rows are sorted by the entity's
primary key before writing so output is deterministic regardless of the
internal order pandas operations happened to produce.

`config.settings` is imported as a module so tests can monkeypatch
`settings.DATA_CURATED_DIR`.
"""

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from config import settings


def curated_batch_dir(batch_id: str) -> Path:
    return settings.DATA_CURATED_DIR / f"batch_id={batch_id}"


def curated_entity_path(entity: str, batch_id: str) -> Path:
    return curated_batch_dir(batch_id) / entity / "data.parquet"


def write_curated_entity(entity: str, batch_id: str, df: pd.DataFrame, sort_by: str) -> Path:
    output_path = curated_entity_path(entity, batch_id)
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing curated output: {output_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    ordered = df.sort_values(sort_by).reset_index(drop=True)
    table = pa.Table.from_pandas(ordered, preserve_index=False)
    pq.write_table(table, output_path)
    return output_path
