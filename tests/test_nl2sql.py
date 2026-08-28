"""Tests for the NL2SQL schema discovery / context generation foundation.

Uses the shared `engine` fixture from conftest.py -- a fresh, throwaway
PostgreSQL database created for this module and dropped afterward. See
conftest.py's docstring for what's required to run these tests.
"""

from src.nl2sql import build_schema_context, discover_schema
from src.warehouse.schema import apply_schema

EXPECTED_TABLES = {"pipeline_batches", "customers", "products", "orders", "order_items", "payments"}

EXPECTED_FOREIGN_KEYS = {
    ("customers", "batch_id", "pipeline_batches", "batch_id"),
    ("products", "batch_id", "pipeline_batches", "batch_id"),
    ("orders", "batch_id", "pipeline_batches", "batch_id"),
    ("orders", "customer_id", "customers", "customer_id"),
    ("order_items", "batch_id", "pipeline_batches", "batch_id"),
    ("order_items", "order_id", "orders", "order_id"),
    ("order_items", "product_id", "products", "product_id"),
    ("payments", "batch_id", "pipeline_batches", "batch_id"),
    ("payments", "order_id", "orders", "order_id"),
}


# ---------------------------------------------------------------------------
# 1. Table discovery
# ---------------------------------------------------------------------------


def test_discovers_all_expected_warehouse_tables(engine):
    apply_schema(engine)
    schema = discover_schema(engine)
    assert EXPECTED_TABLES <= set(schema.table_names)


def test_table_discovery_is_deterministic(engine):
    apply_schema(engine)
    first = discover_schema(engine)
    second = discover_schema(engine)
    assert first == second


# ---------------------------------------------------------------------------
# 2. Columns and data types
# ---------------------------------------------------------------------------


def test_customers_columns_discovered_with_types(engine):
    apply_schema(engine)
    schema = discover_schema(engine)
    customers = schema.table("customers")
    assert customers is not None

    column_names = {c.name for c in customers.columns}
    assert column_names == {
        "customer_id", "full_name", "email", "city", "country", "signup_date", "batch_id",
    }

    customer_id = customers.column("customer_id")
    assert customer_id.is_primary_key
    assert not customer_id.nullable
    assert "VARCHAR" in customer_id.data_type.upper() or "CHAR" in customer_id.data_type.upper()


def test_orders_reconciliation_columns_discovered(engine):
    """The reconciliation fields carried through from Phase 4 must be
    visible to the NL2SQL layer -- queries like "orders that failed
    reconciliation" depend on total_amount_reconciled being known."""
    apply_schema(engine)
    schema = discover_schema(engine)
    orders = schema.table("orders")
    column_names = {c.name for c in orders.columns}
    assert {
        "source_total_amount", "calculated_total_amount",
        "total_amount_difference", "total_amount_reconciled",
    } <= column_names


# ---------------------------------------------------------------------------
# 3. Primary keys
# ---------------------------------------------------------------------------


def test_primary_keys_discovered_for_every_entity_table(engine):
    apply_schema(engine)
    schema = discover_schema(engine)
    expected_pks = {
        "pipeline_batches": ("batch_id",),
        "customers": ("customer_id",),
        "products": ("product_id",),
        "orders": ("order_id",),
        "order_items": ("order_item_id",),
        "payments": ("payment_id",),
    }
    for table_name, pk in expected_pks.items():
        assert schema.table(table_name).primary_key == pk


# ---------------------------------------------------------------------------
# 4. Foreign-key relationships
# ---------------------------------------------------------------------------


def test_foreign_key_relationships_discovered(engine):
    apply_schema(engine)
    schema = discover_schema(engine)

    discovered = {
        (table.name, fk.column, fk.references_table, fk.references_column)
        for table in schema.tables
        for fk in table.foreign_keys
    }
    assert EXPECTED_FOREIGN_KEYS <= discovered


# ---------------------------------------------------------------------------
# 5. Check constraints (enum-like values -- e.g. order status)
# ---------------------------------------------------------------------------


def test_orders_status_check_constraint_discovered(engine):
    apply_schema(engine)
    schema = discover_schema(engine)
    orders = schema.table("orders")
    combined = " ".join(orders.check_constraints)
    assert "PLACED" in combined
    assert "DELIVERED" in combined


# ---------------------------------------------------------------------------
# 6. Schema context generation
# ---------------------------------------------------------------------------


def test_schema_context_includes_every_table_and_its_columns(engine):
    apply_schema(engine)
    schema = discover_schema(engine)
    context = build_schema_context(schema)

    for table in schema.tables:
        assert f"Table: {table.name}" in context
        for column in table.columns:
            assert column.name in context


def test_schema_context_includes_known_relationships_and_descriptions(engine):
    apply_schema(engine)
    schema = discover_schema(engine)
    context = build_schema_context(schema)

    assert "orders.customer_id -> customers.customer_id" in context
    assert "order_items.order_id -> orders.order_id" in context
    # Descriptions sourced from the DDL header comments (see descriptions.py).
    assert "reconciliation" in context.lower()
    assert "pipeline_batches" in context


def test_schema_context_is_deterministic(engine):
    apply_schema(engine)
    schema = discover_schema(engine)
    assert build_schema_context(schema) == build_schema_context(schema)


def test_schema_context_never_leaks_connection_credentials(engine):
    apply_schema(engine)
    schema = discover_schema(engine)
    context = build_schema_context(schema)

    password = engine.url.password
    if password:
        assert password not in context
    assert engine.url.database not in context
