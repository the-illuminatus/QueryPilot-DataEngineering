"""Data-quality / validation pipeline entrypoint.

Validates one specific, already-ingested batch end to end: verifies it
exists, loads all five entities, applies entity-level, referential
(foreign-key), and temporal validation rules, splits every entity's rows
into valid vs. rejected, writes rejected rows and a JSON quality report
under data/rejected/batch_id=<batch_id>/, and logs a summary.

Entities are validated in dependency order (customers, products, then
orders, then order_items and payments), and each foreign-key check is
made against the *accepted* rows of its parent entity, not the raw ones.
A row referencing a parent that exists in the raw file but was itself
rejected (e.g. a duplicate customer_id) is therefore correctly rejected
too -- an "accepted" order can never dangle on a customer that didn't
make it into the accepted customer set.

Rows failing data-quality rules are an *expected*, successful outcome: the
pipeline exits 0 and reports them as quarantined. A pipeline failure --
the batch (or an entity within it) doesn't exist, a raw file is corrupt or
missing expected columns, or this batch has already been validated --
exits non-zero with a clear error instead of guessing or silently
overwriting prior output.

Usage:
    python -m src.validation.pipeline --batch-id <BATCH_ID>
"""

import argparse
import logging
import sys

from src.ingestion.schemas import ENTITIES
from src.validation.accepted import write_accepted_entity
from src.validation.reader import ValidationInputError, load_batch
from src.validation.rejection import build_rejected_rows, rejected_batch_dir, write_rejected_entity
from src.validation.report import build_quality_report, write_quality_report
from src.validation.rules import (
    validate_customers,
    validate_order_items,
    validate_orders,
    validate_payments,
    validate_products,
)

logger = logging.getLogger(__name__)


def run_validation(batch_id: str) -> dict:
    if rejected_batch_dir(batch_id).exists():
        raise ValidationInputError(
            f"Batch '{batch_id}' has already been validated "
            f"({rejected_batch_dir(batch_id)} already exists); refusing to overwrite."
        )

    logger.info("Loading batch_id=%s", batch_id)
    data = load_batch(batch_id)

    logger.info("Applying validation rules")
    customers_violations = validate_customers(data["customers"])
    products_violations = validate_products(data["products"])

    # Foreign-key checks reference only the rows that will actually be
    # accepted -- a row referencing a parent that exists in the raw file
    # but was itself rejected must be rejected too.
    accepted_customers = data["customers"].drop(index=list(customers_violations.keys()))
    accepted_products = data["products"].drop(index=list(products_violations.keys()))

    orders_violations = validate_orders(data["orders"], accepted_customers)
    accepted_orders = data["orders"].drop(index=list(orders_violations.keys()))

    order_items_violations = validate_order_items(data["order_items"], accepted_orders, accepted_products)
    payments_violations = validate_payments(data["payments"], accepted_orders)

    violations = {
        "customers": customers_violations,
        "products": products_violations,
        "orders": orders_violations,
        "order_items": order_items_violations,
        "payments": payments_violations,
    }

    entity_results = {}
    for entity in ENTITIES:
        df = data[entity]
        entity_violations = violations[entity]
        total = len(df)
        rejected_count = len(entity_violations)
        valid_count = total - rejected_count

        reason_counts = {}
        for issues in entity_violations.values():
            for issue in issues:
                reason_counts[issue["code"]] = reason_counts.get(issue["code"], 0) + 1

        entity_results[entity] = {
            "total": total,
            "valid": valid_count,
            "rejected": rejected_count,
            "reason_counts": reason_counts,
        }

        if entity_violations:
            rejected_rows = build_rejected_rows(df, entity_violations, entity, batch_id)
            output_path = write_rejected_entity(entity, batch_id, rejected_rows)
            logger.info("%s: %d/%d rows rejected -> %s", entity, rejected_count, total, output_path)
        else:
            logger.info("%s: 0/%d rows rejected (no output file written)", entity, total)

        # Accepted rows are always written (even when nothing was rejected)
        # so later pipeline stages have a single, reliable hand-off point
        # and never need to re-run validation rules themselves.
        accepted_path = write_accepted_entity(entity, batch_id, df, entity_violations)
        logger.info("%s: %d/%d rows accepted -> %s", entity, valid_count, total, accepted_path)

    report = build_quality_report(batch_id, entity_results)
    report_file = write_quality_report(batch_id, report)
    logger.info(
        "Validation complete batch_id=%s: %d/%d rows valid (%.2f%%). Report: %s",
        batch_id,
        report["valid_rows"],
        report["total_rows"],
        report["quality_percentage"],
        report_file,
    )

    return report


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    parser = argparse.ArgumentParser(
        description="Validate one completed ingestion batch and quarantine bad rows."
    )
    parser.add_argument(
        "--batch-id",
        required=True,
        help="The ingestion batch_id to validate (see data/raw/_batches/).",
    )
    args = parser.parse_args()

    try:
        run_validation(args.batch_id)
    except ValidationInputError as exc:
        logger.error("Validation pipeline failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
