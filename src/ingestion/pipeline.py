"""Ingestion pipeline entrypoint.

For each entity, reads its raw incoming extract, performs structural
validation, lands it into an immutable batch-partitioned raw zone, and
writes a JSON manifest for the run. One batch id is shared across every
entity in a run. A structural failure on one entity is recorded and does
not stop the other, independent entities from being processed.

Usage:
    python -m src.ingestion.pipeline
"""

import logging
from pathlib import Path
from typing import List, Optional

from config import settings
from src.ingestion.batch import create_batch_id
from src.ingestion.loader import land_entity
from src.ingestion.manifest import write_batch_manifest
from src.ingestion.reader import IngestionShapeError, read_raw_file
from src.ingestion.schemas import ENTITIES

logger = logging.getLogger(__name__)


def incoming_path(entity: str) -> Path:
    return settings.DATA_RAW_DIR / "_incoming" / entity / f"{entity}.csv"


def ingest_dataset(entity: str, batch_id: str) -> dict:
    source_path = incoming_path(entity)
    result = {
        "entity": entity,
        "source_file": str(source_path),
        "status": "failed",
        "row_count": 0,
        "output_path": None,
        "columns": [],
        "error": None,
    }
    try:
        df = read_raw_file(entity, source_path)
        output_path = land_entity(entity, df, batch_id)
        result.update(
            status="ok",
            row_count=len(df),
            output_path=str(output_path),
            columns=list(df.columns),
        )
        logger.info("Ingested %s: %d rows -> %s", entity, len(df), output_path)
    except IngestionShapeError as exc:
        result["error"] = str(exc)
        logger.error("Ingestion failed for %s: %s", entity, exc)
    return result


def ingest_all(entities: Optional[List[str]] = None, batch_id: Optional[str] = None) -> dict:
    entities = entities or ENTITIES
    batch_id = batch_id or create_batch_id()
    logger.info("Starting ingestion run batch_id=%s for entities=%s", batch_id, entities)

    results = [ingest_dataset(entity, batch_id) for entity in entities]

    manifest_file = write_batch_manifest(batch_id, results)

    succeeded = sum(1 for r in results if r["status"] == "ok")
    failed = len(results) - succeeded
    logger.info(
        "Ingestion run complete batch_id=%s: %d succeeded, %d failed. Manifest: %s",
        batch_id,
        succeeded,
        failed,
        manifest_file,
    )

    return {"batch_id": batch_id, "manifest_path": str(manifest_file), "results": results}


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    ingest_all()


if __name__ == "__main__":
    main()
