"""Explicit Spark read schemas and the curated output contract.

Every validated CSV is read with an explicit ``StructType`` -- no
``inferSchema``. Ingestion/validation deliberately keep every value as a
string (see ``src/ingestion/reader.py``); this stage is where types are
asserted, so the read schema is all-string and casting happens explicitly
in ``transform.py`` (a cast that fails becomes a null and is caught, the
same "validation already passed, so a failure here is a pipeline bug"
stance V1's ``src/transformation/types.py`` takes).

``CURATED_COLUMNS`` is the exact column set (and order) the existing
warehouse loader expects per entity -- it mirrors the upsert statements in
``src/warehouse/loader.py``. ``promote_curated`` sorts to this before
writing so V2 curated Parquet is indistinguishable from V1's.
"""

from __future__ import annotations

from pyspark.sql.types import StringType, StructField, StructType

ENTITIES = ("customers", "products", "orders", "order_items", "payments")

# --- validated-CSV read schemas (all string; matches src/ingestion/schemas.py) ---

_STR = StringType()


def _schema(*names: str) -> StructType:
    return StructType([StructField(name, _STR, True) for name in names])


READ_SCHEMAS = {
    "customers": _schema("customer_id", "full_name", "email", "city", "state", "signup_date"),
    "products": _schema("product_id", "product_name", "category", "price"),
    "orders": _schema("order_id", "customer_id", "order_date", "status", "total_amount"),
    "order_items": _schema("order_item_id", "order_id", "product_id", "quantity", "unit_price"),
    "payments": _schema(
        "payment_id", "order_id", "payment_date", "payment_method", "payment_status", "amount"
    ),
}

# --- curated output contract (must match src/warehouse/loader.py upserts) ---

CURATED_COLUMNS = {
    "customers": ["customer_id", "full_name", "email", "city", "state", "signup_date"],
    "products": ["product_id", "product_name", "category", "price"],
    "orders": [
        "order_id",
        "customer_id",
        "order_date",
        "status",
        "source_total_amount",
        "calculated_total_amount",
        "total_amount_difference",
        "total_amount_reconciled",
    ],
    "order_items": [
        "order_item_id",
        "order_id",
        "product_id",
        "quantity",
        "unit_price",
        "line_total",
    ],
    "payments": [
        "payment_id",
        "order_id",
        "payment_date",
        "payment_method",
        "payment_status",
        "amount",
    ],
}

# Primary key per entity -- promote_curated sorts on this so output row
# order is deterministic (same as V1's src/transformation/writer.py).
PRIMARY_KEY = {
    "customers": "customer_id",
    "products": "product_id",
    "orders": "order_id",
    "order_items": "order_item_id",
    "payments": "payment_id",
}

# Reconciliation tolerance -- identical to V1
# (src/transformation/business.py RECONCILIATION_TOLERANCE).
RECONCILIATION_TOLERANCE = 0.01
