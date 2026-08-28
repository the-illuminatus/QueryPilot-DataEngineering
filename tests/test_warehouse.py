"""Tests for the PostgreSQL warehouse loader.

Uses the shared `engine` fixture from conftest.py -- a fresh, throwaway
PostgreSQL database created for this module and dropped afterward. See
conftest.py's docstring for what's required to run these tests.
"""

import uuid

import pandas as pd
import pytest
from sqlalchemy import text

from config import settings
from src.warehouse.lineage import get_batch_status
from src.warehouse.loader import load_entity
from src.warehouse.pipeline import run_warehouse_load
from src.warehouse.reader import WarehouseInputError
from src.warehouse.schema import apply_schema
from tests.conftest import _write_curated_batch


def _typed_fixture_batch():
    """A small, fully-typed fixture matching what Phase 4 would hand off --
    dtypes matter here since these go straight to psycopg2 parameter
    binding."""
    customers = pd.DataFrame(
        [{"customer_id": "TC1", "full_name": "Alice", "email": "alice@x.com", "city": "Pune", "state": "Maharashtra",
          "signup_date": pd.Timestamp("2024-01-01")}]
    )
    products = pd.DataFrame(
        [{"product_id": "TP1", "product_name": "Widget", "category": "Gadgets", "price": 9.99}]
    )
    orders = pd.DataFrame(
        [{"order_id": "TO1", "customer_id": "TC1", "order_date": pd.Timestamp("2024-02-01"), "status": "PLACED",
          "source_total_amount": 19.98, "calculated_total_amount": 19.98,
          "total_amount_difference": 0.0, "total_amount_reconciled": True}]
    )
    order_items = pd.DataFrame(
        [{"order_item_id": "TOI1", "order_id": "TO1", "product_id": "TP1", "quantity": 2, "unit_price": 9.99,
          "line_total": 19.98}]
    )
    payments = pd.DataFrame(
        [{"payment_id": "TPAY1", "order_id": "TO1", "payment_date": pd.Timestamp("2024-02-02"),
          "payment_method": "CREDIT_CARD", "payment_status": "SUCCESS", "amount": 19.98}]
    )
    return {
        "customers": customers,
        "products": products,
        "orders": orders,
        "order_items": order_items,
        "payments": payments,
    }


# ---------------------------------------------------------------------------
# 1 & 2. DDL / schema creation, table existence
# ---------------------------------------------------------------------------


def test_apply_schema_creates_all_expected_tables(engine):
    apply_schema(engine)
    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            )
        }
    expected = {"pipeline_batches", "customers", "products", "orders", "order_items", "payments"}
    assert expected <= tables


def test_apply_schema_is_idempotent(engine):
    apply_schema(engine)
    apply_schema(engine)  # must not raise


# ---------------------------------------------------------------------------
# 3. Primary keys
# ---------------------------------------------------------------------------


def test_primary_key_rejects_duplicate(engine):
    apply_schema(engine)
    batch_id = f"pk-test-{uuid.uuid4().hex[:8]}"
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO pipeline_batches (batch_id, status, started_at) "
                "VALUES (:b, 'SUCCESS', now())"
            ),
            {"b": batch_id},
        )
        conn.execute(
            text(
                "INSERT INTO products (product_id, product_name, category, price, batch_id) "
                "VALUES ('DUPPROD', 'A', 'Cat', 1.0, :b)"
            ),
            {"b": batch_id},
        )
    with pytest.raises(Exception):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO products (product_id, product_name, category, price, batch_id) "
                    "VALUES ('DUPPROD', 'B', 'Cat', 2.0, :b)"
                ),
                {"b": batch_id},
            )


# ---------------------------------------------------------------------------
# 4. Foreign keys
# ---------------------------------------------------------------------------


def test_foreign_key_rejects_orphan_reference(engine):
    apply_schema(engine)
    batch_id = f"fk-test-{uuid.uuid4().hex[:8]}"
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO pipeline_batches (batch_id, status, started_at) VALUES (:b, 'SUCCESS', now())"),
            {"b": batch_id},
        )
    with pytest.raises(Exception):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO orders (order_id, customer_id, order_date, status, "
                    "source_total_amount, calculated_total_amount, total_amount_difference, "
                    "total_amount_reconciled, batch_id) "
                    "VALUES ('ORPHAN', 'NO_SUCH_CUSTOMER', '2024-01-01', 'PLACED', 1, 1, 0, true, :b)"
                ),
                {"b": batch_id},
            )


# ---------------------------------------------------------------------------
# 5, 6. Loading a controlled batch + row-count reconciliation
# ---------------------------------------------------------------------------


def test_load_controlled_batch_end_to_end(engine, monkeypatch, tmp_path):
    apply_schema(engine)
    batch_id = f"load-test-{uuid.uuid4().hex[:8]}"
    _write_curated_batch(batch_id, _typed_fixture_batch(), monkeypatch, tmp_path)

    report = run_warehouse_load(batch_id, engine=engine)

    assert report["status"] == "SUCCESS"
    assert report["total_rows"] == 5  # 1 row per entity in the fixture
    for entity, counts in report["entities"].items():
        assert counts["loaded"] == counts["curated_rows"]

    row_counts = report["quality_checks"]["row_counts"]
    for entity, counts in row_counts.items():
        assert counts["actual"] == counts["expected"]


# ---------------------------------------------------------------------------
# 7. Idempotent second load
# ---------------------------------------------------------------------------


def test_rerunning_same_batch_is_refused(engine, monkeypatch, tmp_path):
    apply_schema(engine)
    batch_id = f"rerun-test-{uuid.uuid4().hex[:8]}"
    _write_curated_batch(batch_id, _typed_fixture_batch(), monkeypatch, tmp_path)

    run_warehouse_load(batch_id, engine=engine)

    with pytest.raises(WarehouseInputError):
        run_warehouse_load(batch_id, engine=engine)

    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM customers WHERE customer_id = 'TC1' AND batch_id = :b"),
            {"b": batch_id},
        ).scalar()
    assert count == 1  # not duplicated


def test_upsert_itself_is_idempotent_independent_of_the_guard(engine):
    """Loads the same records twice via load_entity() directly, bypassing
    the pipeline's batch-already-loaded guard entirely, to prove the SQL
    upsert mechanism doesn't duplicate rows on its own merits either."""
    apply_schema(engine)
    batch_id = f"upsert-test-{uuid.uuid4().hex[:8]}"
    df = pd.DataFrame(
        [{"product_id": "UPSERT1", "product_name": "A", "category": "Cat", "price": 1.0}]
    )
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO pipeline_batches (batch_id, status, started_at) VALUES (:b, 'SUCCESS', now())"),
            {"b": batch_id},
        )
        load_entity(conn, "products", df, batch_id)
        load_entity(conn, "products", df, batch_id)

    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM products WHERE product_id = 'UPSERT1'")
        ).scalar()
    assert count == 1


# ---------------------------------------------------------------------------
# 8. Failed load rollback
# ---------------------------------------------------------------------------


def test_failed_load_rolls_back_and_records_failure(engine, monkeypatch, tmp_path):
    apply_schema(engine)
    batch_id = f"fail-test-{uuid.uuid4().hex[:8]}"

    frames = _typed_fixture_batch()
    # Corrupt order_items to reference a product that doesn't exist in
    # this batch's products -- a genuine FK violation at load time.
    frames["order_items"] = pd.DataFrame(
        [{"order_item_id": "TOI1", "order_id": "TO1", "product_id": "NONEXISTENT", "quantity": 2,
          "unit_price": 9.99, "line_total": 19.98}]
    )
    _write_curated_batch(batch_id, frames, monkeypatch, tmp_path)

    with pytest.raises(Exception):
        run_warehouse_load(batch_id, engine=engine)

    with engine.connect() as conn:
        # customers/products/orders upserted before the failing statement
        # must all have been rolled back too -- nothing partial survives.
        customer_count = conn.execute(
            text("SELECT COUNT(*) FROM customers WHERE customer_id = 'TC1' AND batch_id = :b"),
            {"b": batch_id},
        ).scalar()
    assert customer_count == 0

    assert get_batch_status(engine, batch_id) == "FAILED"


# ---------------------------------------------------------------------------
# 9. Batch lineage
# ---------------------------------------------------------------------------


def test_batch_lineage_recorded(engine, monkeypatch, tmp_path):
    apply_schema(engine)
    batch_id = f"lineage-test-{uuid.uuid4().hex[:8]}"
    _write_curated_batch(batch_id, _typed_fixture_batch(), monkeypatch, tmp_path)

    run_warehouse_load(batch_id, engine=engine)

    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT status, loaded_row_count, curated_row_count, started_at, completed_at "
                "FROM pipeline_batches WHERE batch_id = :b"
            ),
            {"b": batch_id},
        ).fetchone()
    assert row is not None
    assert row.status == "SUCCESS"
    assert row.loaded_row_count == 5
    assert row.curated_row_count == 5
    assert row.started_at is not None
    assert row.completed_at is not None

    with engine.connect() as conn:
        customer_batch_id = conn.execute(
            text("SELECT batch_id FROM customers WHERE customer_id = 'TC1'")
        ).scalar()
    assert customer_batch_id == batch_id


# ---------------------------------------------------------------------------
# 10. Analytical query execution
# ---------------------------------------------------------------------------


def test_analytical_queries_execute_without_error(engine, monkeypatch, tmp_path):
    apply_schema(engine)
    batch_id = f"analytics-test-{uuid.uuid4().hex[:8]}"
    _write_curated_batch(batch_id, _typed_fixture_batch(), monkeypatch, tmp_path)
    run_warehouse_load(batch_id, engine=engine)

    analytics_dir = settings.PROJECT_ROOT / "sql" / "analytics"
    sql_files = sorted(analytics_dir.glob("*.sql"))
    assert len(sql_files) >= 10

    with engine.connect() as conn:
        for path in sql_files:
            conn.execute(text(path.read_text()))  # must not raise
