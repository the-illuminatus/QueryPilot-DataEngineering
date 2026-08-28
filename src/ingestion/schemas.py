"""Expected raw-file schemas for each entity, per the Phase 2 dataset contract.

Used only for structural validation at ingestion time (column presence).
Value-level data quality is a later pipeline stage and is deliberately
out of scope here.
"""

EXPECTED_COLUMNS = {
    "customers": ["customer_id", "full_name", "email", "city", "state", "signup_date"],
    "products": ["product_id", "product_name", "category", "price"],
    "orders": ["order_id", "customer_id", "order_date", "status", "total_amount"],
    "order_items": ["order_item_id", "order_id", "product_id", "quantity", "unit_price"],
    "payments": [
        "payment_id",
        "order_id",
        "payment_date",
        "payment_method",
        "payment_status",
        "amount",
    ],
}

ENTITIES = list(EXPECTED_COLUMNS.keys())
