"""QueryPilot V2 pipeline DAG -- Airflow orchestration over the existing
Python pipeline logic, with PySpark for the transformation step.

Airflow here is **orchestration only**: every task is a thin call into
code that already lives in ``src/`` and is already tested. No business
rule is reimplemented in this file.

Task graph::

    generate_or_stage_raw   (src.ingestion.pipeline.ingest_all)
            |   batch_id (XCom)
    validate                (src.validation.pipeline.run_validation)
            |
    pyspark_transform       (src.spark_transform.pipeline.run_spark_transform -- Spark)
            |
    write_curated           (src.spark_transform.pipeline.promote_curated)
            |
    load_postgres           (src.warehouse.pipeline.run_warehouse_load)
            |
    quality_check           (assert pipeline_batches = SUCCESS + reconciliation)

Storage is the local filesystem (the repo's ``data/`` tree, bind-mounted
into the container). The warehouse is the existing PostgreSQL instance,
reached at ``POSTGRES_HOST`` (``host.docker.internal`` from the compose
file). No S3, no object storage, no cloud services.

V1 is unaffected: its four ``python -m src.<stage>.pipeline`` commands
still run standalone with the V1 dependency set and never touch Airflow or
Spark.
"""

from __future__ import annotations

import os
import sys

import pendulum
from airflow.decorators import dag, task

# The repo is bind-mounted here by docker-compose.airflow.yml and also put
# on PYTHONPATH; this insert makes the DAG import-safe regardless.
_PROJECT_ROOT = os.getenv("QUERYPILOT_PROJECT_ROOT", "/opt/project")
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

_DEFAULT_ARGS = {
    "retries": 1,
    "retry_delay": pendulum.duration(minutes=1),
}


@dag(
    dag_id="querypilot_data_pipeline",
    description="V2: Airflow-orchestrated PySpark pipeline (local, zero cloud).",
    schedule=None,  # manual trigger -- this is a portfolio/demo pipeline
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args=_DEFAULT_ARGS,
    tags=["querypilot", "v2", "pyspark"],
    doc_md=__doc__,
)
def querypilot_data_pipeline():
    @task
    def generate_or_stage_raw() -> str:
        """Ingest the committed source extracts into an immutable raw
        batch (V1 ingestion). Returns the new batch_id via XCom."""
        from src.ingestion.pipeline import ingest_all

        run = ingest_all()
        failed = [r["entity"] for r in run["results"] if r["status"] != "ok"]
        if failed:
            raise RuntimeError(f"Ingestion failed for entities: {failed}")
        return run["batch_id"]

    @task
    def validate(batch_id: str) -> str:
        """Entity / referential / temporal validation (V1). Rejected rows
        are an expected outcome, not a failure."""
        from src.validation.pipeline import run_validation

        report = run_validation(batch_id)
        print(
            f"validation: {report['valid_rows']}/{report['total_rows']} rows valid "
            f"({report['quality_percentage']}%)"
        )
        return batch_id

    @task
    def pyspark_transform(batch_id: str) -> str:
        """The Spark step: explicit schemas, referential semi-joins,
        filtering, derived columns, and the reconciliation group-by
        aggregation. Writes staged Parquet."""
        from src.spark_transform.pipeline import run_spark_transform

        summary = run_spark_transform(batch_id)
        recon = summary["order_total_reconciliation"]
        print(f"spark transform: orders reconciled {recon['reconciled']}/{recon['orders_checked']}")
        return batch_id

    @task
    def write_curated(batch_id: str) -> str:
        """Materialise the V1 curated contract (one ``data.parquet`` per
        entity) + ``transformation_report.json`` from the staged Parquet,
        reusing V1's writer/report modules."""
        from src.spark_transform.pipeline import promote_curated

        promote_curated(batch_id)
        return batch_id

    @task
    def load_postgres(batch_id: str) -> str:
        """Upsert the curated batch into the existing PostgreSQL warehouse
        (V1 loader, unchanged) -- idempotent, transactional, with batch
        lineage."""
        from src.warehouse.pipeline import run_warehouse_load

        report = run_warehouse_load(batch_id)
        print(f"warehouse load: {report['total_rows']} rows, status {report['status']}")
        return batch_id

    @task
    def quality_check(batch_id: str) -> None:
        """Confirm the batch landed cleanly: lineage row is SUCCESS and
        the order-reconciliation query runs against the warehouse."""
        from sqlalchemy import text

        from config import settings
        from src.warehouse.db import get_engine

        engine = get_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT status, loaded_row_count FROM pipeline_batches WHERE batch_id = :b"
                ),
                {"b": batch_id},
            ).fetchone()
            if row is None:
                raise RuntimeError(f"No pipeline_batches row for {batch_id}")
            if row.status != "SUCCESS":
                raise RuntimeError(f"batch {batch_id} status is {row.status!r}, expected SUCCESS")

            recon_sql = (
                settings.PROJECT_ROOT / "sql" / "analytics" / "09_order_reconciliation_rate.sql"
            ).read_text()
            recon = conn.execute(text(recon_sql)).fetchone()

        print(
            f"quality_check OK: {batch_id} loaded {row.loaded_row_count} rows; "
            f"reconciliation rate {recon.reconciliation_rate_pct}% "
            f"({recon.reconciled_orders}/{recon.total_orders} orders)"
        )

    raw = generate_or_stage_raw()
    validated = validate(raw)
    transformed = pyspark_transform(validated)
    curated = write_curated(transformed)
    loaded = load_postgres(curated)
    quality_check(loaded)


querypilot_data_pipeline()
