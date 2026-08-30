"""V2 PySpark transformation path for the QueryPilot pipeline.

This package is the Spark-based equivalent of ``src/transformation`` (V1's
pandas transformation stage). It is **additive**: V1's
``src.transformation.pipeline`` is untouched and still runs standalone.
The V2 pipeline (orchestrated by the Airflow DAG ``querypilot_data_pipeline``)
uses this package for the transformation-heavy step instead.

Flow (per already-ingested, already-validated ``batch_id``):

    data/validated/batch_id=<id>/<entity>.csv     (V1 validation output)
        -> run_spark_transform(batch_id)          (this package, Spark)
    data/spark_staging/batch_id=<id>/<entity>.parquet
        -> promote_curated(batch_id)              (this package, pandas)
    data/curated/batch_id=<id>/<entity>/data.parquet   (V1 curated contract)
    data/curated/batch_id=<id>/transformation_report.json

``promote_curated`` reuses V1's ``src.transformation.writer`` and
``src.transformation.report`` so the curated output is byte-for-byte the
same shape V1 produces and the existing warehouse loader / dashboard keep
working with no changes.

Spark does the real work: explicit schemas, CSV reads, referential
semi-joins across all five entities, row filtering, derived columns
(``line_total``), and the group-by aggregation that reconciles each
order's recorded total against the sum of its line items. Only the final,
already-reduced result is converted to pandas for the single-file Parquet
sink (V1's curated contract is one file per entity, not a Spark part-file
directory).
"""

from src.spark_transform.pipeline import (
    SparkTransformError,
    promote_curated,
    run_spark_transform,
)

__all__ = ["run_spark_transform", "promote_curated", "SparkTransformError"]
