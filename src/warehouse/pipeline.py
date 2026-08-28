"""Warehouse loading pipeline entrypoint.

Loads one specific curated batch into PostgreSQL: applies the warehouse
schema (idempotent DDL), upserts each entity table in dependency order
within a single transaction, records batch lineage in pipeline_batches,
runs post-load reconciliation checks, and writes a JSON load report.

Loading strategy: INSERT ... ON CONFLICT (natural primary key) DO UPDATE.
This keeps entity tables at "current state" (standard SCD Type 1
dimension/fact behavior) -- re-running the same batch_id is a true no-op
at the SQL level, and loading a different batch that happens to share
natural keys with an earlier one updates rows in place rather than
duplicating them (and never touches rows whose keys don't overlap, so it
can never "destroy" an unrelated batch's rows the way a blind
truncate-and-reload would). Full historical lineage of every load
*attempt* -- not just current row state -- is preserved separately in
pipeline_batches, which is never overwritten or truncated wholesale. A
row's own batch_id column always reflects the batch that most recently
produced its current state; pipeline_batches is the permanent record of
every batch ever loaded, including ones since superseded.

Idempotency guard: a batch_id already marked SUCCESS in pipeline_batches
is refused outright (consistent with every earlier pipeline stage)
rather than relying solely on upsert semantics -- fast, explicit, and
predictable. A batch that previously FAILED may be retried freely, since
a failed load's transaction was fully rolled back and left no partial
data behind.

Transaction safety: all table upserts, the post-load reconciliation
checks, and the final pipeline_batches SUCCESS update happen in one
transaction. Any failure rolls the whole thing back -- no batch is ever
left partially loaded or incorrectly marked successful -- and a FAILED
record is then written in a separate, already-committed transaction so
the failure is durably visible for retry.

Usage:
    python -m src.warehouse.pipeline --batch-id <BATCH_ID>
"""

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.engine import Engine

from src.warehouse.db import get_engine
from src.warehouse.lineage import get_batch_status, insert_batch_record, mark_batch_success, record_batch_failure
from src.warehouse.loader import load_entity
from src.warehouse.quality import (
    WarehouseQualityError,
    verify_monetary_total,
    verify_no_orphan_foreign_keys,
    verify_no_unexpected_nulls,
    verify_primary_key_uniqueness,
    verify_row_counts,
)
from src.warehouse.reader import WarehouseInputError, load_curated_batch
from src.warehouse.report import build_load_report, write_load_report
from src.warehouse.schema import apply_schema

logger = logging.getLogger(__name__)

LOAD_ORDER = ["customers", "products", "orders", "order_items", "payments"]

PRIMARY_KEYS = {
    "customers": "customer_id",
    "products": "product_id",
    "orders": "order_id",
    "order_items": "order_item_id",
    "payments": "payment_id",
}

REQUIRED_NON_NULL_COLUMNS = {
    "customers": ["customer_id", "full_name", "email", "city", "state", "signup_date"],
    "products": ["product_id", "product_name", "category", "price"],
    "orders": ["order_id", "customer_id", "order_date", "status", "source_total_amount"],
    "order_items": ["order_item_id", "order_id", "product_id", "quantity", "unit_price", "line_total"],
    "payments": ["payment_id", "order_id", "payment_date", "payment_method", "payment_status", "amount"],
}

FOREIGN_KEYS = [
    ("orders", "customer_id", "customers", "customer_id"),
    ("order_items", "order_id", "orders", "order_id"),
    ("order_items", "product_id", "products", "product_id"),
    ("payments", "order_id", "orders", "order_id"),
]


def run_warehouse_load(batch_id: str, engine: Optional[Engine] = None) -> dict:
    engine = engine or get_engine()
    started_at = datetime.now(timezone.utc)
    start_time = time.monotonic()

    logger.info("Applying warehouse schema (idempotent)")
    apply_schema(engine)

    existing_status = get_batch_status(engine, batch_id)
    if existing_status == "SUCCESS":
        raise WarehouseInputError(
            f"Batch '{batch_id}' has already been successfully loaded into the warehouse; "
            f"refusing to reprocess."
        )

    logger.info("Loading curated Parquet for batch_id=%s", batch_id)
    curated = load_curated_batch(batch_id)
    curated_row_count = sum(len(df) for df in curated.values())

    entity_results = {}
    warnings = []

    try:
        with engine.begin() as conn:
            insert_batch_record(conn, batch_id, curated_row_count)

            for entity in LOAD_ORDER:
                df = curated[entity]
                loaded_count = load_entity(conn, entity, df, batch_id)
                entity_results[entity] = {"curated_rows": len(df), "loaded": loaded_count}
                logger.info("%s: upserted %d rows", entity, loaded_count)

            logger.info("Running post-load reconciliation checks")
            quality_checks = {
                "row_counts": verify_row_counts(
                    conn, {e: r["curated_rows"] for e, r in entity_results.items()}, batch_id
                )
            }

            for table, pk in PRIMARY_KEYS.items():
                verify_primary_key_uniqueness(conn, table, pk)
            for child_table, fk_column, parent_table, parent_pk in FOREIGN_KEYS:
                verify_no_orphan_foreign_keys(conn, child_table, fk_column, parent_table, parent_pk)
            for table, columns in REQUIRED_NON_NULL_COLUMNS.items():
                verify_no_unexpected_nulls(conn, table, columns)

            quality_checks["monetary_totals"] = {
                "orders.source_total_amount": verify_monetary_total(
                    conn,
                    "orders",
                    "source_total_amount",
                    batch_id,
                    float(curated["orders"]["source_total_amount"].sum()),
                ),
                "payments.amount": verify_monetary_total(
                    conn, "payments", "amount", batch_id, float(curated["payments"]["amount"].sum())
                ),
            }

            total_loaded = sum(r["loaded"] for r in entity_results.values())
            mark_batch_success(conn, batch_id, total_loaded)
    except Exception as exc:
        logger.error("Warehouse load failed for batch_id=%s: %s", batch_id, exc)
        record_batch_failure(engine, batch_id, str(exc))
        completed_at = datetime.now(timezone.utc)
        report = build_load_report(
            batch_id,
            "FAILED",
            started_at.isoformat(),
            completed_at.isoformat(),
            round(time.monotonic() - start_time, 3),
            entity_results,
            {},
            warnings,
            error=str(exc),
        )
        write_load_report(batch_id, report)
        raise

    completed_at = datetime.now(timezone.utc)
    report = build_load_report(
        batch_id,
        "SUCCESS",
        started_at.isoformat(),
        completed_at.isoformat(),
        round(time.monotonic() - start_time, 3),
        entity_results,
        quality_checks,
        warnings,
    )
    report_file = write_load_report(batch_id, report)
    logger.info(
        "Warehouse load complete batch_id=%s: %d rows loaded across %d tables. Report: %s",
        batch_id,
        report["total_rows"],
        len(entity_results),
        report_file,
    )
    return report


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    parser = argparse.ArgumentParser(
        description="Load one curated batch into the PostgreSQL warehouse."
    )
    parser.add_argument("--batch-id", required=True, help="The curated batch_id to load.")
    args = parser.parse_args()

    try:
        run_warehouse_load(args.batch_id)
    except (WarehouseInputError, WarehouseQualityError) as exc:
        logger.error("Warehouse pipeline failed: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.error("Warehouse pipeline failed with an unexpected database error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
