"""Transformation pipeline entrypoint.

Reads the already-validated (accepted) rows of one specific batch, casts
them into proper analytical types, applies the approved business
transformations (order_items.line_total, orders total reconciliation),
writes curated Parquet under data/curated/batch_id=<batch_id>/, verifies
the output, and writes a transformation report.

Never re-runs Phase 3's validation rules -- this stage only reads what
validation already decided was valid.

A business reconciliation mismatch (an order's source and calculated
totals disagree) is an expected, measurable data condition, not a
pipeline failure: it's recorded in the report and the pipeline still
exits 0. A pipeline failure -- the batch hasn't been validated yet, a
value that passed validation still fails to cast, a schema/quality check
fails, or curated output already exists for this batch -- exits non-zero
instead of guessing or silently overwriting prior output.

Usage:
    python -m src.transformation.pipeline --batch-id <BATCH_ID>
"""

import argparse
import logging
import sys

from src.ingestion.schemas import ENTITIES
from src.transformation.business import add_line_total, reconcile_order_totals
from src.transformation.quality import (
    ParquetQualityError,
    verify_dtypes,
    verify_line_totals,
    verify_no_unexpected_nulls,
    verify_order_reconciliation_consistency,
    verify_parquet_file,
)
from src.transformation.reader import TransformationInputError, load_accepted_batch
from src.transformation.report import build_transformation_report, write_transformation_report
from src.transformation.types import (
    TransformationTypeError,
    cast_customers,
    cast_order_items,
    cast_orders,
    cast_payments,
    cast_products,
)
from src.transformation.writer import curated_batch_dir, write_curated_entity

logger = logging.getLogger(__name__)

SORT_KEYS = {
    "customers": "customer_id",
    "products": "product_id",
    "orders": "order_id",
    "order_items": "order_item_id",
    "payments": "payment_id",
}


def run_transformation(batch_id: str) -> dict:
    if curated_batch_dir(batch_id).exists():
        raise TransformationInputError(
            f"Batch '{batch_id}' has already been transformed "
            f"({curated_batch_dir(batch_id)} already exists); refusing to overwrite."
        )

    logger.info("Loading accepted rows for batch_id=%s", batch_id)
    accepted = load_accepted_batch(batch_id)
    input_counts = {entity: len(df) for entity, df in accepted.items()}

    logger.info("Casting types")
    typed = {
        "customers": cast_customers(accepted["customers"]),
        "products": cast_products(accepted["products"]),
        "orders": cast_orders(accepted["orders"]),
        "order_items": cast_order_items(accepted["order_items"]),
        "payments": cast_payments(accepted["payments"]),
    }

    logger.info("Applying business transformations")
    typed["order_items"] = add_line_total(typed["order_items"])
    typed["orders"] = reconcile_order_totals(typed["orders"], typed["order_items"])

    warnings = []
    entity_results = {}

    for entity in ENTITIES:
        df = typed[entity]

        verify_dtypes(df, entity)
        verify_no_unexpected_nulls(df, entity)
        if entity == "order_items":
            verify_line_totals(df)
        if entity == "orders":
            verify_order_reconciliation_consistency(df)

        output_path = write_curated_entity(entity, batch_id, df, SORT_KEYS[entity])
        verify_parquet_file(entity, output_path, len(df))

        entity_results[entity] = {"input_valid_rows": input_counts[entity], "output_rows": len(df)}
        logger.info("%s: %d rows -> %s", entity, len(df), output_path)

        if input_counts[entity] != len(df):
            warnings.append(
                f"{entity}: input row count ({input_counts[entity]}) != output row count ({len(df)})"
            )

    orders_df = typed["orders"]
    reconciled_count = int(orders_df["total_amount_reconciled"].sum())
    non_reconciled_df = orders_df[~orders_df["total_amount_reconciled"]]
    order_reconciliation = {
        "orders_checked": len(orders_df),
        "reconciled": reconciled_count,
        "non_reconciled": len(non_reconciled_df),
        "non_reconciled_order_ids": non_reconciled_df["order_id"].tolist(),
    }

    if order_reconciliation["non_reconciled"]:
        warnings.append(
            f"orders: {order_reconciliation['non_reconciled']} order(s) did not reconcile "
            f"against their order_items"
        )

    report = build_transformation_report(batch_id, entity_results, order_reconciliation, warnings)
    report_file = write_transformation_report(batch_id, report)
    logger.info(
        "Transformation complete batch_id=%s: orders reconciled %d/%d. Report: %s",
        batch_id,
        reconciled_count,
        len(orders_df),
        report_file,
    )

    return report


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    parser = argparse.ArgumentParser(
        description="Transform one validated batch's accepted rows into curated Parquet."
    )
    parser.add_argument(
        "--batch-id",
        required=True,
        help="The batch_id to transform (must already have validation output under data/validated/).",
    )
    args = parser.parse_args()

    try:
        run_transformation(args.batch_id)
    except (TransformationInputError, TransformationTypeError, ParquetQualityError) as exc:
        logger.error("Transformation pipeline failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
