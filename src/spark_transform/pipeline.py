"""V2 Spark transformation pipeline: entrypoint, staging, and promotion.

Two steps, deliberately separable so the Airflow DAG can run them as two
tasks (``pyspark_transform`` then ``write_curated``):

* ``run_spark_transform(batch_id)`` -- Spark reads the validated CSVs,
  runs ``transform.transform_batch``, and writes each curated entity to a
  neutral staging Parquet at ``data/spark_staging/batch_id=<id>/``. Spark
  is the only thing that touches the data here.
* ``promote_curated(batch_id)`` -- pandas reads the staging Parquet and
  writes the canonical ``data/curated/batch_id=<id>/<entity>/data.parquet``
  layout **using V1's own writer and report modules**, so the curated
  output and ``transformation_report.json`` are identical in shape to what
  ``src/transformation/pipeline.py`` produces. The existing warehouse
  loader and dashboard need no changes.

Run standalone (does both steps -- handy for local testing without Airflow):

    python -m src.spark_transform.pipeline --batch-id <BATCH_ID>

The DAG instead calls ``run_spark_transform`` and ``promote_curated``
directly, as separate tasks.

Storage is the local filesystem throughout -- the same ``data/`` tree V1
uses. No object storage, no cloud.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pyspark.sql import SparkSession

from config import settings
from src.spark_transform.schemas import CURATED_COLUMNS, ENTITIES, PRIMARY_KEY, READ_SCHEMAS
from src.spark_transform.session import build_spark_session, stop_spark_session
from src.spark_transform.transform import transform_batch
from src.transformation.report import build_transformation_report, write_transformation_report
from src.transformation.writer import curated_batch_dir, write_curated_entity
from src.validation.accepted import accepted_entity_path

logger = logging.getLogger(__name__)

_DATE_COLUMNS = {
    "customers": ["signup_date"],
    "products": [],
    "orders": ["order_date"],
    "order_items": [],
    "payments": ["payment_date"],
}
_STATS_FILE = "_reconciliation_stats.json"
_INPUT_COUNTS_FILE = "_input_counts.json"


class SparkTransformError(Exception):
    """Raised when the V2 transformation cannot begin or complete: the
    batch has not been validated, staging/curated output already exists,
    or a staging file is missing. A pipeline failure -- distinct from a
    business reconciliation mismatch, which is an expected, recorded
    outcome (as in V1)."""


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------


def spark_staging_dir(batch_id: str) -> Path:
    """Neutral hand-off between the Spark step and the promote step. Kept
    outside ``data/curated/`` so V1's ``curated_batch_dir`` guard is not
    confused by it. Gitignored."""
    return settings.DATA_CURATED_DIR.parent / "spark_staging" / f"batch_id={batch_id}"


def staging_entity_path(entity: str, batch_id: str) -> Path:
    return spark_staging_dir(batch_id) / f"{entity}.parquet"


# --------------------------------------------------------------------------
# Step 1 -- Spark transform -> staging
# --------------------------------------------------------------------------


def run_spark_transform(batch_id: str, spark: Optional[SparkSession] = None) -> dict:
    """Reads the validated batch, runs the Spark transformation, and
    stages the five curated entity frames as Parquet. Returns a summary
    dict (row counts + reconciliation stats)."""
    missing = [e for e in ENTITIES if not accepted_entity_path(e, batch_id).exists()]
    if missing:
        raise SparkTransformError(
            f"Batch '{batch_id}' has no validated output for entities: {missing}. "
            f"Run `python -m src.validation.pipeline --batch-id {batch_id}` first."
        )
    if spark_staging_dir(batch_id).exists():
        raise SparkTransformError(
            f"Spark staging for batch '{batch_id}' already exists "
            f"({spark_staging_dir(batch_id)}); refusing to overwrite."
        )

    owns_session = spark is None
    spark = spark or build_spark_session()
    try:
        logger.info("Reading validated batch_id=%s with explicit schemas", batch_id)
        frames = {
            entity: spark.read.csv(
                str(accepted_entity_path(entity, batch_id)),
                header=True,
                schema=READ_SCHEMAS[entity],
                mode="FAILFAST",
            )
            for entity in ENTITIES
        }
        input_counts = {entity: df.count() for entity, df in frames.items()}

        logger.info("Running Spark transformation (joins, filters, reconciliation aggregation)")
        curated, stats = transform_batch(frames)

        staging = spark_staging_dir(batch_id)
        staging.mkdir(parents=True, exist_ok=True)
        output_counts = {}
        for entity in ENTITIES:
            pdf = curated[entity].toPandas()
            pdf = pdf[CURATED_COLUMNS[entity]]
            table = pa.Table.from_pandas(pdf, preserve_index=False)
            pq.write_table(table, staging_entity_path(entity, batch_id))
            output_counts[entity] = len(pdf)
            logger.info("%s: %d rows staged", entity, len(pdf))

        (staging / _STATS_FILE).write_text(json.dumps(stats, indent=2))
        (staging / _INPUT_COUNTS_FILE).write_text(json.dumps(input_counts, indent=2))
    finally:
        if owns_session:
            stop_spark_session(spark)

    logger.info(
        "Spark transform complete batch_id=%s: orders reconciled %d/%d",
        batch_id,
        stats["reconciled"],
        stats["orders_checked"],
    )
    return {
        "batch_id": batch_id,
        "staging_dir": str(spark_staging_dir(batch_id)),
        "input_counts": input_counts,
        "output_counts": output_counts,
        "order_total_reconciliation": stats,
    }


# --------------------------------------------------------------------------
# Step 2 -- staging -> canonical curated (V1 contract) + report
# --------------------------------------------------------------------------


def _coerce_for_curated(pdf: pd.DataFrame, entity: str) -> pd.DataFrame:
    out = pdf.copy()
    for column in _DATE_COLUMNS[entity]:
        out[column] = pd.to_datetime(out[column])
    if entity == "order_items":
        out["quantity"] = out["quantity"].astype("int64")
    return out


def promote_curated(batch_id: str) -> dict:
    """Reads the staged Parquet and writes the canonical curated layout
    plus ``transformation_report.json``, reusing V1's writer/report code."""
    staging = spark_staging_dir(batch_id)
    missing = [e for e in ENTITIES if not staging_entity_path(e, batch_id).exists()]
    if missing:
        raise SparkTransformError(
            f"Spark staging for batch '{batch_id}' is missing entities: {missing}. "
            f"Run the Spark transform step first."
        )
    if curated_batch_dir(batch_id).exists():
        raise SparkTransformError(
            f"Batch '{batch_id}' already has curated output "
            f"({curated_batch_dir(batch_id)}); refusing to overwrite."
        )

    stats = json.loads((staging / _STATS_FILE).read_text())
    input_counts = json.loads((staging / _INPUT_COUNTS_FILE).read_text())

    entity_results = {}
    warnings = []
    for entity in ENTITIES:
        pdf = _coerce_for_curated(pd.read_parquet(staging_entity_path(entity, batch_id)), entity)
        output_path = write_curated_entity(entity, batch_id, pdf, PRIMARY_KEY[entity])
        entity_results[entity] = {
            "input_valid_rows": int(input_counts.get(entity, 0)),
            "output_rows": len(pdf),
        }
        logger.info("%s: %d rows -> %s", entity, len(pdf), output_path)
        if input_counts.get(entity, 0) != len(pdf):
            warnings.append(
                f"{entity}: validated row count ({input_counts.get(entity)}) != "
                f"curated row count ({len(pdf)}) (rows dropped by Spark referential/domain filters)"
            )

    if stats["non_reconciled"]:
        warnings.append(
            f"orders: {stats['non_reconciled']} order(s) did not reconcile against their order_items"
        )

    report = build_transformation_report(batch_id, entity_results, stats, warnings)
    # Mark which engine produced this batch -- V1's report has no such
    # field, so an extra key is additive and harmless to existing readers.
    report["engine"] = "pyspark"
    report["promoted_at"] = datetime.now(timezone.utc).isoformat()
    report_file = write_transformation_report(batch_id, report)
    logger.info("Curated output written for batch_id=%s. Report: %s", batch_id, report_file)
    return {"batch_id": batch_id, "curated_dir": str(curated_batch_dir(batch_id)), "report": report}


def run_full(batch_id: str) -> dict:
    """Both steps in one process -- the standalone / local path."""
    stage = run_spark_transform(batch_id)
    promote = promote_curated(batch_id)
    return {"stage": stage, "promote": promote}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="V2 PySpark transformation for one validated batch (local, no cloud)."
    )
    parser.add_argument("--batch-id", required=True, help="The validated batch_id to transform.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--stage-only", action="store_true", help="Run only the Spark transform -> staging step."
    )
    group.add_argument(
        "--promote-only", action="store_true", help="Run only the staging -> curated promotion step."
    )
    args = parser.parse_args()

    try:
        if args.stage_only:
            run_spark_transform(args.batch_id)
        elif args.promote_only:
            promote_curated(args.batch_id)
        else:
            run_full(args.batch_id)
    except SparkTransformError as exc:
        logger.error("Spark transformation pipeline failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
