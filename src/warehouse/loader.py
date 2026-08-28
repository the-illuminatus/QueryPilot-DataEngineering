"""Bulk upsert loading of each entity into its warehouse table.

Uses INSERT ... ON CONFLICT (<natural primary key>) DO UPDATE. Loading the
same logical row again -- whether via a batch re-run or a later batch
touching the same entities -- updates it in place rather than duplicating
it. This is standard "current state" (SCD Type 1) dimension/fact-table
behavior; full historical lineage of every load *attempt* is preserved
separately in pipeline_batches, not by keeping duplicate row copies here.
See src/warehouse/pipeline.py for the full loading-strategy rationale.

Each entity is loaded as a single bulk statement (one call to
Connection.execute() with a list of parameter dicts, which SQLAlchemy
sends as an executemany), not row by row.
"""

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

CUSTOMERS_UPSERT = text(
    """
    INSERT INTO customers (customer_id, full_name, email, city, state, signup_date, batch_id)
    VALUES (:customer_id, :full_name, :email, :city, :state, :signup_date, :batch_id)
    ON CONFLICT (customer_id) DO UPDATE SET
        full_name = EXCLUDED.full_name,
        email = EXCLUDED.email,
        city = EXCLUDED.city,
        state = EXCLUDED.state,
        signup_date = EXCLUDED.signup_date,
        batch_id = EXCLUDED.batch_id
    """
)

PRODUCTS_UPSERT = text(
    """
    INSERT INTO products (product_id, product_name, category, price, batch_id)
    VALUES (:product_id, :product_name, :category, :price, :batch_id)
    ON CONFLICT (product_id) DO UPDATE SET
        product_name = EXCLUDED.product_name,
        category = EXCLUDED.category,
        price = EXCLUDED.price,
        batch_id = EXCLUDED.batch_id
    """
)

ORDERS_UPSERT = text(
    """
    INSERT INTO orders (
        order_id, customer_id, order_date, status,
        source_total_amount, calculated_total_amount, total_amount_difference, total_amount_reconciled,
        batch_id
    )
    VALUES (
        :order_id, :customer_id, :order_date, :status,
        :source_total_amount, :calculated_total_amount, :total_amount_difference, :total_amount_reconciled,
        :batch_id
    )
    ON CONFLICT (order_id) DO UPDATE SET
        customer_id = EXCLUDED.customer_id,
        order_date = EXCLUDED.order_date,
        status = EXCLUDED.status,
        source_total_amount = EXCLUDED.source_total_amount,
        calculated_total_amount = EXCLUDED.calculated_total_amount,
        total_amount_difference = EXCLUDED.total_amount_difference,
        total_amount_reconciled = EXCLUDED.total_amount_reconciled,
        batch_id = EXCLUDED.batch_id
    """
)

ORDER_ITEMS_UPSERT = text(
    """
    INSERT INTO order_items (order_item_id, order_id, product_id, quantity, unit_price, line_total, batch_id)
    VALUES (:order_item_id, :order_id, :product_id, :quantity, :unit_price, :line_total, :batch_id)
    ON CONFLICT (order_item_id) DO UPDATE SET
        order_id = EXCLUDED.order_id,
        product_id = EXCLUDED.product_id,
        quantity = EXCLUDED.quantity,
        unit_price = EXCLUDED.unit_price,
        line_total = EXCLUDED.line_total,
        batch_id = EXCLUDED.batch_id
    """
)

PAYMENTS_UPSERT = text(
    """
    INSERT INTO payments (payment_id, order_id, payment_date, payment_method, payment_status, amount, batch_id)
    VALUES (:payment_id, :order_id, :payment_date, :payment_method, :payment_status, :amount, :batch_id)
    ON CONFLICT (payment_id) DO UPDATE SET
        order_id = EXCLUDED.order_id,
        payment_date = EXCLUDED.payment_date,
        payment_method = EXCLUDED.payment_method,
        payment_status = EXCLUDED.payment_status,
        amount = EXCLUDED.amount,
        batch_id = EXCLUDED.batch_id
    """
)

UPSERT_STATEMENTS = {
    "customers": CUSTOMERS_UPSERT,
    "products": PRODUCTS_UPSERT,
    "orders": ORDERS_UPSERT,
    "order_items": ORDER_ITEMS_UPSERT,
    "payments": PAYMENTS_UPSERT,
}


def _to_native(value):
    # psycopg2 does not know how to adapt numpy scalar types (int64,
    # float64, bool_) out of the box -- convert them to their native
    # Python equivalents before binding as query parameters. pandas
    # Timestamp is left as-is; it subclasses datetime.datetime, which
    # psycopg2 handles natively.
    if isinstance(value, np.generic):
        return value.item()
    return value


def _records(df: pd.DataFrame, batch_id: str) -> list:
    records = []
    for row in df.to_dict(orient="records"):
        record = {key: _to_native(value) for key, value in row.items()}
        record["batch_id"] = batch_id
        records.append(record)
    return records


def load_entity(conn: Connection, entity: str, df: pd.DataFrame, batch_id: str) -> int:
    records = _records(df, batch_id)
    if not records:
        return 0
    conn.execute(UPSERT_STATEMENTS[entity], records)
    return len(records)
