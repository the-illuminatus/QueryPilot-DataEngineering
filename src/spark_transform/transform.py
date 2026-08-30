"""The Spark transformation itself -- pure DataFrame in, DataFrame out.

No file I/O, no SparkSession creation, no Airflow. `transform_batch` takes
the five raw (all-string) validated DataFrames and returns the five
curated DataFrames plus a reconciliation stats dict. That makes it
directly unit-testable with tiny in-memory frames (see
tests/test_spark_transform.py).

What Spark actually does here (this is the "transformation-heavy part"
the V2 design calls for -- not an import-Spark-then-go-to-pandas shim):

* cast every column from string to its real type, explicitly;
* referential **semi-joins** so the curated set is self-consistent -- an
  order whose customer didn't survive is dropped, then order_items and
  payments are filtered to the orders that remain, and order_items are
  also filtered to products that exist;
* row **filters** for the numeric domain rules (quantity > 0, prices > 0,
  amounts >= 0) -- defence in depth on top of V1 validation;
* a derived column, ``order_items.line_total = quantity * unit_price``;
* a **group-by aggregation** -- sum of ``line_total`` per order -- joined
  back onto orders to produce ``calculated_total_amount`` and the
  reconciliation columns, exactly matching V1's
  ``src/transformation/business.reconcile_order_totals``.

The reconciliation logic and tolerance are kept identical to V1 on
purpose: the two transformation paths must agree on what "reconciled"
means.
"""

from __future__ import annotations

from typing import Dict, Tuple

from pyspark.sql import DataFrame, functions as F

from src.spark_transform.schemas import CURATED_COLUMNS, RECONCILIATION_TOLERANCE

_ORDER_STATUSES = ["PLACED", "SHIPPED", "DELIVERED", "CANCELLED", "RETURNED"]
_PAYMENT_METHODS = ["CREDIT_CARD", "DEBIT_CARD", "UPI", "NET_BANKING", "WALLET", "COD"]
_PAYMENT_STATUSES = ["SUCCESS", "FAILED", "PENDING", "REFUNDED"]


def _non_null(df: DataFrame, *columns: str) -> DataFrame:
    """Drop rows with a null in any of the named (required) columns."""
    condition = None
    for column in columns:
        c = F.col(column).isNotNull()
        condition = c if condition is None else (condition & c)
    return df.filter(condition) if condition is not None else df


def transform_batch(frames: Dict[str, DataFrame]) -> Tuple[Dict[str, DataFrame], dict]:
    """frames: {entity: raw all-string DataFrame} for all five entities.
    Returns ({entity: curated DataFrame}, reconciliation_stats)."""
    customers = _transform_customers(frames["customers"])
    products = _transform_products(frames["products"])

    # Orders first, filtered to customers that survived -> then everything
    # that references an order is filtered to the orders that survived.
    orders_base = _transform_orders_base(frames["orders"]).join(
        customers.select("customer_id"), on="customer_id", how="left_semi"
    )

    order_items = _transform_order_items(
        frames["order_items"], orders_base.select("order_id"), products.select("product_id")
    )

    orders = _reconcile_orders(orders_base, order_items)

    payments = _transform_payments(
        frames["payments"], orders.select("order_id")
    )

    curated = {
        "customers": _select_curated(customers, "customers"),
        "products": _select_curated(products, "products"),
        "orders": _select_curated(orders, "orders"),
        "order_items": _select_curated(order_items, "order_items"),
        "payments": _select_curated(payments, "payments"),
    }

    reconciled = orders.filter(F.col("total_amount_reconciled")).count()
    total_orders = orders.count()
    non_reconciled_ids = [
        r["order_id"]
        for r in orders.filter(~F.col("total_amount_reconciled"))
        .select("order_id")
        .orderBy("order_id")
        .collect()
    ]
    stats = {
        "orders_checked": total_orders,
        "reconciled": reconciled,
        "non_reconciled": total_orders - reconciled,
        "non_reconciled_order_ids": non_reconciled_ids,
    }
    return curated, stats


def _select_curated(df: DataFrame, entity: str) -> DataFrame:
    return df.select(*CURATED_COLUMNS[entity])


def _transform_customers(df: DataFrame) -> DataFrame:
    out = (
        df.withColumn("signup_date", F.to_date("signup_date"))
        .transform(lambda d: _non_null(d, "customer_id", "full_name", "email", "city", "state", "signup_date"))
        .dropDuplicates(["customer_id"])
    )
    return out


def _transform_products(df: DataFrame) -> DataFrame:
    out = (
        df.withColumn("price", F.col("price").cast("double"))
        .transform(lambda d: _non_null(d, "product_id", "product_name", "category", "price"))
        .filter(F.col("price") >= 0)
        .dropDuplicates(["product_id"])
    )
    return out


def _transform_orders_base(df: DataFrame) -> DataFrame:
    out = (
        df.withColumn("order_date", F.to_date("order_date"))
        .withColumn("source_total_amount", F.col("total_amount").cast("double"))
        .transform(lambda d: _non_null(d, "order_id", "customer_id", "order_date", "status", "source_total_amount"))
        .filter(F.col("status").isin(_ORDER_STATUSES))
        .filter(F.col("source_total_amount") >= 0)
        .dropDuplicates(["order_id"])
        .select("order_id", "customer_id", "order_date", "status", "source_total_amount")
    )
    return out


def _transform_order_items(
    df: DataFrame, valid_orders: DataFrame, valid_products: DataFrame
) -> DataFrame:
    out = (
        df.withColumn("quantity", F.col("quantity").cast("int"))
        .withColumn("unit_price", F.col("unit_price").cast("double"))
        .transform(lambda d: _non_null(d, "order_item_id", "order_id", "product_id", "quantity", "unit_price"))
        .filter(F.col("quantity") > 0)
        .filter(F.col("unit_price") > 0)
        .dropDuplicates(["order_item_id"])
        .join(valid_orders, on="order_id", how="left_semi")
        .join(valid_products, on="product_id", how="left_semi")
        .withColumn("line_total", F.round(F.col("quantity") * F.col("unit_price"), 2))
    )
    return out


def _reconcile_orders(orders_base: DataFrame, order_items: DataFrame) -> DataFrame:
    calculated = order_items.groupBy("order_id").agg(
        F.round(F.sum("line_total"), 2).alias("calculated_total_amount")
    )
    out = (
        orders_base.join(calculated, on="order_id", how="left")
        .withColumn(
            "calculated_total_amount",
            F.round(F.coalesce(F.col("calculated_total_amount"), F.lit(0.0)), 2),
        )
        .withColumn(
            "total_amount_difference",
            F.round(F.col("source_total_amount") - F.col("calculated_total_amount"), 2),
        )
        .withColumn(
            "total_amount_reconciled",
            F.abs(F.col("total_amount_difference")) <= F.lit(RECONCILIATION_TOLERANCE),
        )
    )
    return out


def _transform_payments(df: DataFrame, valid_orders: DataFrame) -> DataFrame:
    out = (
        df.withColumn("payment_date", F.to_date("payment_date"))
        .withColumn("amount", F.col("amount").cast("double"))
        .transform(
            lambda d: _non_null(
                d, "payment_id", "order_id", "payment_date", "payment_method", "payment_status", "amount"
            )
        )
        .filter(F.col("payment_method").isin(_PAYMENT_METHODS))
        .filter(F.col("payment_status").isin(_PAYMENT_STATUSES))
        .filter(F.col("amount") >= 0)
        .dropDuplicates(["payment_id"])
        .join(valid_orders, on="order_id", how="left_semi")
    )
    return out
