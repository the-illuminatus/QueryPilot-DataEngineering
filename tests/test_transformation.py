"""Tests for the transformation pipeline.

Unit-level tests exercise casting and business-transform functions
directly against small in-memory DataFrames. Pipeline-level tests use
isolated tmp_path fixtures and monkeypatch `config.settings.DATA_VALIDATED_DIR`
/ `DATA_CURATED_DIR`. None of this depends on the full 9,800-row dataset,
and none of it re-runs Phase 3's validation rules.
"""

import pandas as pd
import pyarrow.parquet as pq
import pytest


def _read_parquet_file(path):
    # pq.ParquetFile reads the file's own schema/data directly. The
    # higher-level pq.read_table()/pyarrow.dataset API instead infers Hive
    # -style partition columns from any "key=value" path segment -- which
    # "batch_id=<batch_id>" intentionally is, for lineage-aware readers --
    # so it would inject an extra "batch_id" column here that isn't part
    # of the file's actual schema. Use ParquetFile when comparing pure
    # data content.
    return pq.ParquetFile(path).read().to_pandas()

from config import settings
from src.ingestion.schemas import EXPECTED_COLUMNS
from src.transformation.business import add_line_total, reconcile_order_totals
from src.transformation.pipeline import run_transformation
from src.transformation.quality import ParquetQualityError, verify_dtypes
from src.transformation.reader import TransformationInputError
from src.transformation.types import cast_customers, cast_order_items, cast_orders, cast_products
from src.transformation.writer import curated_entity_path


def _df(rows, entity):
    return pd.DataFrame(rows, columns=EXPECTED_COLUMNS[entity])


# ---------------------------------------------------------------------------
# Type normalization
# ---------------------------------------------------------------------------


def test_numeric_type_conversion():
    df = _df(
        [{"product_id": "P1", "product_name": "Widget", "category": "Gadgets", "price": "9.99"}], "products"
    )
    typed = cast_products(df)
    assert typed["price"].dtype == "float64"
    assert typed["price"].iloc[0] == 9.99


def test_date_conversion():
    df = _df(
        [
            {
                "customer_id": "C1",
                "full_name": "Alice",
                "email": "a@x.com",
                "city": "Pune",
                "state": "Maharashtra",
                "signup_date": "2024-01-01",
            }
        ],
        "customers",
    )
    typed = cast_customers(df)
    assert str(typed["signup_date"].dtype).startswith("datetime64")
    assert typed["signup_date"].iloc[0] == pd.Timestamp("2024-01-01")


# ---------------------------------------------------------------------------
# Business transformations
# ---------------------------------------------------------------------------


def test_line_total_calculation():
    order_items = _df(
        [{"order_item_id": "OI1", "order_id": "O1", "product_id": "P1", "quantity": "3", "unit_price": "10.0"}],
        "order_items",
    )
    typed = cast_order_items(order_items)
    result = add_line_total(typed)
    assert result["line_total"].iloc[0] == 30.0


def test_order_total_aggregation_and_reconciliation_match():
    orders = _df(
        [{"order_id": "O1", "customer_id": "C1", "order_date": "2024-01-01", "status": "PLACED", "total_amount": "30.0"}],
        "orders",
    )
    order_items = _df(
        [{"order_item_id": "OI1", "order_id": "O1", "product_id": "P1", "quantity": "3", "unit_price": "10.0"}],
        "order_items",
    )
    typed_orders = cast_orders(orders)
    typed_items = add_line_total(cast_order_items(order_items))

    result = reconcile_order_totals(typed_orders, typed_items)
    row = result.iloc[0]
    assert row["source_total_amount"] == 30.0
    assert row["calculated_total_amount"] == 30.0
    assert row["total_amount_difference"] == 0.0
    assert bool(row["total_amount_reconciled"]) is True


def test_reconciliation_mismatch_is_observable_not_silently_fixed():
    orders = _df(
        [{"order_id": "O1", "customer_id": "C1", "order_date": "2024-01-01", "status": "PLACED", "total_amount": "999.0"}],
        "orders",
    )
    order_items = _df(
        [{"order_item_id": "OI1", "order_id": "O1", "product_id": "P1", "quantity": "3", "unit_price": "10.0"}],
        "order_items",
    )
    typed_orders = cast_orders(orders)
    typed_items = add_line_total(cast_order_items(order_items))

    result = reconcile_order_totals(typed_orders, typed_items)
    row = result.iloc[0]
    assert row["source_total_amount"] == 999.0  # preserved, not overwritten
    assert row["calculated_total_amount"] == 30.0
    assert row["total_amount_difference"] == 969.0
    assert bool(row["total_amount_reconciled"]) is False


def test_order_with_no_matching_order_items_gets_zero_calculated_total():
    orders = _df(
        [{"order_id": "O1", "customer_id": "C1", "order_date": "2024-01-01", "status": "PLACED", "total_amount": "5.0"}],
        "orders",
    )
    order_items = _df([], "order_items")
    typed_orders = cast_orders(orders)
    typed_items = add_line_total(cast_order_items(order_items))
    result = reconcile_order_totals(typed_orders, typed_items)
    assert result.iloc[0]["calculated_total_amount"] == 0.0
    assert bool(result.iloc[0]["total_amount_reconciled"]) is False


# ---------------------------------------------------------------------------
# Schema verification
# ---------------------------------------------------------------------------


def test_transformed_schema_passes_verification():
    df = _df(
        [{"product_id": "P1", "product_name": "Widget", "category": "Gadgets", "price": "9.99"}], "products"
    )
    typed = cast_products(df)
    verify_dtypes(typed, "products")  # must not raise


def test_transformed_schema_rejects_wrong_dtype():
    df = pd.DataFrame(
        [{"product_id": "P1", "product_name": "Widget", "category": "Gadgets", "price": "9.99"}]
    )
    with pytest.raises(ParquetQualityError):
        verify_dtypes(df, "products")  # price is still a string, not float64


# ---------------------------------------------------------------------------
# Pipeline-level tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_dirs(tmp_path, monkeypatch):
    validated_dir = tmp_path / "data" / "validated"
    curated_dir = tmp_path / "data" / "curated"
    monkeypatch.setattr(settings, "DATA_VALIDATED_DIR", validated_dir)
    monkeypatch.setattr(settings, "DATA_CURATED_DIR", curated_dir)
    return validated_dir, curated_dir


def _write_validated_batch(validated_dir, batch_id, entity_frames):
    for entity, df in entity_frames.items():
        path = validated_dir / f"batch_id={batch_id}" / f"{entity}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)


def _small_fixture_batch():
    customers = _df(
        [
            {
                "customer_id": "C1",
                "full_name": "Alice",
                "email": "alice@x.com",
                "city": "Pune",
                "state": "Maharashtra",
                "signup_date": "2024-01-01",
            }
        ],
        "customers",
    )
    products = _df(
        [{"product_id": "P1", "product_name": "Widget", "category": "Gadgets", "price": "9.99"}], "products"
    )
    orders = _df(
        [
            {"order_id": "O1", "customer_id": "C1", "order_date": "2024-02-01", "status": "PLACED", "total_amount": "19.98"},
            {"order_id": "O2", "customer_id": "C1", "order_date": "2024-03-01", "status": "PLACED", "total_amount": "999.0"},
        ],
        "orders",
    )
    order_items = _df(
        [{"order_item_id": "OI1", "order_id": "O1", "product_id": "P1", "quantity": "2", "unit_price": "9.99"}],
        "order_items",
    )
    payments = _df(
        [
            {
                "payment_id": "PAY1",
                "order_id": "O1",
                "payment_date": "2024-02-02",
                "payment_method": "CREDIT_CARD",
                "payment_status": "SUCCESS",
                "amount": "19.98",
            }
        ],
        "payments",
    )
    return {
        "customers": customers,
        "products": products,
        "orders": orders,
        "order_items": order_items,
        "payments": payments,
    }


def test_missing_validated_batch_fails_clearly():
    with pytest.raises(TransformationInputError):
        run_transformation("nonexistent-batch")


def test_end_to_end_transformation_writes_parquet_and_report(isolated_dirs):
    validated_dir, _curated_dir = isolated_dirs
    batch_id = "batchABC"
    _write_validated_batch(validated_dir, batch_id, _small_fixture_batch())

    report = run_transformation(batch_id)

    assert report["batch_id"] == batch_id
    assert report["entities"]["orders"]["input_valid_rows"] == 2
    assert report["entities"]["orders"]["output_rows"] == 2
    assert report["order_total_reconciliation"]["orders_checked"] == 2
    assert report["order_total_reconciliation"]["reconciled"] == 1
    assert report["order_total_reconciliation"]["non_reconciled"] == 1
    assert "O2" in report["order_total_reconciliation"]["non_reconciled_order_ids"]

    for entity in ("customers", "products", "orders", "order_items", "payments"):
        path = curated_entity_path(entity, batch_id)
        assert path.exists()
        assert f"batch_id={batch_id}" in str(path)

    order_items_df = _read_parquet_file(curated_entity_path("order_items", batch_id))
    assert len(order_items_df) == 1
    assert "line_total" in order_items_df.columns


def test_row_counts_match_input_and_output(isolated_dirs):
    validated_dir, _curated_dir = isolated_dirs
    batch_id = "batchABC"
    _write_validated_batch(validated_dir, batch_id, _small_fixture_batch())
    report = run_transformation(batch_id)
    for counts in report["entities"].values():
        assert counts["input_valid_rows"] == counts["output_rows"]
    assert report["warnings"] == ["orders: 1 order(s) did not reconcile against their order_items"]


def test_rerunning_same_batch_fails_and_does_not_overwrite(isolated_dirs):
    validated_dir, curated_dir = isolated_dirs
    batch_id = "batchABC"
    _write_validated_batch(validated_dir, batch_id, _small_fixture_batch())
    run_transformation(batch_id)

    report_file = curated_dir / f"batch_id={batch_id}" / "transformation_report.json"
    original = report_file.read_text()

    with pytest.raises(TransformationInputError):
        run_transformation(batch_id)

    assert report_file.read_text() == original


def test_transformation_is_deterministic(isolated_dirs):
    validated_dir, _curated_dir = isolated_dirs
    fixture = _small_fixture_batch()

    _write_validated_batch(validated_dir, "batch1", fixture)
    run_transformation("batch1")

    _write_validated_batch(validated_dir, "batch2", fixture)
    run_transformation("batch2")

    for entity in ("customers", "products", "orders", "order_items", "payments"):
        df1 = _read_parquet_file(curated_entity_path(entity, "batch1"))
        df2 = _read_parquet_file(curated_entity_path(entity, "batch2"))
        pd.testing.assert_frame_equal(df1, df2)
