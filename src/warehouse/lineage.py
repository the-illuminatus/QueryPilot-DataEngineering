"""Reads and writes the pipeline_batches lineage/audit table.

IN_PROGRESS is written and updated to SUCCESS within the same load
transaction, so it is never durably visible on its own -- only SUCCESS
(committed) or FAILED (written separately, after a rollback) ever
persist. This table's history is therefore always truthful: it never
shows a batch as "in progress" after the process that was loading it has
finished, one way or another.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine


def get_batch_status(engine: Engine, batch_id: str) -> Optional[str]:
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT status FROM pipeline_batches WHERE batch_id = :batch_id"),
            {"batch_id": batch_id},
        ).fetchone()
    return result[0] if result else None


def insert_batch_record(conn: Connection, batch_id: str, curated_row_count: int) -> None:
    conn.execute(
        text(
            """
            INSERT INTO pipeline_batches (batch_id, status, started_at, curated_row_count)
            VALUES (:batch_id, 'IN_PROGRESS', :started_at, :curated_row_count)
            ON CONFLICT (batch_id) DO UPDATE SET
                status = 'IN_PROGRESS',
                started_at = :started_at,
                curated_row_count = :curated_row_count,
                completed_at = NULL,
                error_message = NULL
            """
        ),
        {
            "batch_id": batch_id,
            "started_at": datetime.now(timezone.utc),
            "curated_row_count": curated_row_count,
        },
    )


def mark_batch_success(conn: Connection, batch_id: str, loaded_row_count: int) -> None:
    conn.execute(
        text(
            """
            UPDATE pipeline_batches
            SET status = 'SUCCESS', completed_at = :completed_at, loaded_row_count = :loaded_row_count
            WHERE batch_id = :batch_id
            """
        ),
        {
            "batch_id": batch_id,
            "completed_at": datetime.now(timezone.utc),
            "loaded_row_count": loaded_row_count,
        },
    )


def record_batch_failure(engine: Engine, batch_id: str, error_message: str) -> None:
    """Writes a FAILED record in its own, separate transaction -- called
    after the main load transaction has already been rolled back, so the
    failure is durably visible even though the attempted data changes are
    not."""
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO pipeline_batches (batch_id, status, started_at, completed_at, error_message)
                VALUES (:batch_id, 'FAILED', :now, :now, :error_message)
                ON CONFLICT (batch_id) DO UPDATE SET
                    status = 'FAILED', completed_at = :now, error_message = :error_message
                """
            ),
            {"batch_id": batch_id, "now": datetime.now(timezone.utc), "error_message": error_message[:2000]},
        )
