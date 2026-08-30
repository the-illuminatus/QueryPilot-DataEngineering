"""Tests for the V2 PySpark transformation path (src/spark_transform).

These are additive -- they do not touch any V1 test. The whole module
skips cleanly (like tests/conftest.py does for PostgreSQL) if PySpark or a
working local Spark/JVM is not available, so `pytest` on a machine without
Java still passes.

Covered:
  * explicit read schemas / curated output contract
  * derived column: order_items.line_total
  * reconciliation group-by aggregation + the reconciled flag (and its
    tolerance), matched against V1's semantics
  * referential semi-join filtering across entities
  * numeric-domain row filtering
  * end-to-end run_spark_transform -> promote_curated producing curated
    Parquet in the exact shape the warehouse loader consumes
"""

from __future__ import annotations

import pandas as pd
import pytest

pyspark = pytest.importorskip("pyspark", reason="pyspark not installed")

from config import settings  # noqa: E402
from src.spark_transform.schemas import CURATED_COLUMNS, READ_SCHEMAS  # noqa: E402
from src.spark_transform.transform import transform_batch  # noqa: E402


@pytest.fixture(scope="module")
def spark():
    from src.spark_transform.session import build_spark_session, stop_spark_session

    try:
        # local[1] + 1 shuffle partition: tiny fixtures, no point paying
        # multi-core task-scheduling overhead per assertion.
        session = build_spark_session(
            app_name="querypilot-spark-tests", shuffle_partitions=1, master="local[1]"
        )
        session.sparkContext.setLogLevel("ERROR")
        # Force the JVM/gateway to actually come up now, so a broken local
        # Spark skips the module instead of failing every test.
        session.range(1).count()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"local Spark/JVM not available for these tests: {exc}")
    yield session
    stop_spark_session(session)


# --- fixture data (raw, all-string, matching the validated-CSV shape) ------


def _base_rows():
    customers = [
        ("C1", "Asha Rao", "asha@x.com", "Pune", "Maharashtra", "2024-01-01"),
        ("C2", "Ravi Kumar", "ravi@x.com", "Chennai", "Tamil Nadu", "2024-02-01"),
    ]
    products = [
        ("P1", "Widget", "Home & Kitchen", "100.0"),
        ("P2", "Gadget", "Electronics", "250.0"),
    ]
    orders = [
        # order_id, customer_id, order_date, status, total_amount
        ("O1", "C1", "2024-03-01", "DELIVERED", "450.00"),  # reconciles: 2*100 + 1*250
        ("O2", "C2", "2024-03-05", "PLACED", "999.00"),     # will NOT reconcile
    ]
    order_items = [
        # order_item_id, order_id, product_id, quantity, unit_price
        ("OI1", "O1", "P1", "2", "100.0"),
        ("OI2", "O1", "P2", "1", "250.0"),
        ("OI3", "O2", "P1", "3", "100.0"),
    ]
    payments = [
        # payment_id, order_id, payment_date, payment_method, payment_status, amount
        ("PAY1", "O1", "2024-03-02", "UPI", "SUCCESS", "450.00"),
        ("PAY2", "O2", "2024-03-06", "CREDIT_CARD", "FAILED", "999.00"),
    ]
    return {
        "customers": customers,
        "products": products,
        "orders": orders,
        "order_items": order_items,
        "payments": payments,
    }


def _frames(spark, rows):
    return {
        entity: spark.createDataFrame(rows[entity], schema=READ_SCHEMAS[entity])
        for entity in rows
    }


def _rows_by_key(df, key):
    return {r[key]: r.asDict() for r in df.collect()}


# --- tests ---------------------------------------------------------------


def test_curated_output_columns_match_contract(spark):
    curated, _ = transform_batch(_frames(spark, _base_rows()))
    for entity, expected in CURATED_COLUMNS.items():
        assert curated[entity].columns == expected


def test_line_total_is_quantity_times_unit_price(spark):
    curated, _ = transform_batch(_frames(spark, _base_rows()))
    items = _rows_by_key(curated["order_items"], "order_item_id")
    assert items["OI1"]["line_total"] == pytest.approx(200.0)
    assert items["OI2"]["line_total"] == pytest.approx(250.0)
    assert items["OI3"]["line_total"] == pytest.approx(300.0)


def test_order_reconciliation_aggregation_and_flag(spark):
    curated, stats = transform_batch(_frames(spark, _base_rows()))
    orders = _rows_by_key(curated["orders"], "order_id")

    assert orders["O1"]["calculated_total_amount"] == pytest.approx(450.0)
    assert orders["O1"]["source_total_amount"] == pytest.approx(450.0)
    assert orders["O1"]["total_amount_difference"] == pytest.approx(0.0)
    assert bool(orders["O1"]["total_amount_reconciled"]) is True

    assert orders["O2"]["calculated_total_amount"] == pytest.approx(300.0)
    assert orders["O2"]["total_amount_difference"] == pytest.approx(699.0)
    assert bool(orders["O2"]["total_amount_reconciled"]) is False

    assert stats == {
        "orders_checked": 2,
        "reconciled": 1,
        "non_reconciled": 1,
        "non_reconciled_order_ids": ["O2"],
    }


def test_reconciliation_tolerance_is_one_paisa(spark):
    rows = _base_rows()
    # O1 recorded total off by exactly 0.01 -> still reconciled.
    rows["orders"][0] = ("O1", "C1", "2024-03-01", "DELIVERED", "450.01")
    curated, _ = transform_batch(_frames(spark, rows))
    orders = _rows_by_key(curated["orders"], "order_id")
    assert bool(orders["O1"]["total_amount_reconciled"]) is True

    rows["orders"][0] = ("O1", "C1", "2024-03-01", "DELIVERED", "450.02")
    curated, _ = transform_batch(_frames(spark, rows))
    orders = _rows_by_key(curated["orders"], "order_id")
    assert bool(orders["O1"]["total_amount_reconciled"]) is False


def test_referential_and_domain_filtering(spark):
    """One pass with every kind of bad row, asserting each is dropped:
    unknown-order line item, unknown-product line item, an order on an
    unknown customer (which must also cascade to its items and payments),
    non-positive quantities, and a payment on an unknown order."""
    rows = _base_rows()
    rows["order_items"].append(("OI_BADORD", "O_NOPE", "P1", "1", "100.0"))
    rows["order_items"].append(("OI_BADPROD", "O1", "P_NOPE", "1", "100.0"))
    rows["order_items"].append(("OI_ZERO", "O1", "P1", "0", "100.0"))
    rows["order_items"].append(("OI_NEG", "O1", "P1", "-2", "100.0"))
    rows["orders"].append(("O3", "C_NOPE", "2024-03-09", "PLACED", "100.0"))
    rows["order_items"].append(("OI_CASCADE", "O3", "P1", "1", "100.0"))
    rows["payments"].append(("PAY_CASCADE", "O3", "2024-03-10", "UPI", "SUCCESS", "100.0"))
    rows["payments"].append(("PAY_BADORD", "O_NOPE", "2024-03-10", "UPI", "SUCCESS", "10.0"))

    curated, _ = transform_batch(_frames(spark, rows))

    item_ids = {r["order_item_id"] for r in curated["order_items"].collect()}
    order_ids = {r["order_id"] for r in curated["orders"].collect()}
    payment_ids = {r["payment_id"] for r in curated["payments"].collect()}

    assert item_ids == {"OI1", "OI2", "OI3"}  # every injected bad item dropped
    assert order_ids == {"O1", "O2"}  # unknown-customer order dropped
    assert payment_ids == {"PAY1", "PAY2"}  # cascaded + unknown-order payment dropped


def test_end_to_end_run_and_promote_produces_loader_ready_curated(spark, tmp_path, monkeypatch):
    from src.spark_transform.pipeline import promote_curated, run_spark_transform

    batch_id = "spark-it-0001"
    validated_dir = tmp_path / "validated"
    curated_dir = tmp_path / "curated"
    monkeypatch.setattr(settings, "DATA_VALIDATED_DIR", validated_dir)
    monkeypatch.setattr(settings, "DATA_CURATED_DIR", curated_dir)

    rows = _base_rows()
    header = {
        "customers": ["customer_id", "full_name", "email", "city", "state", "signup_date"],
        "products": ["product_id", "product_name", "category", "price"],
        "orders": ["order_id", "customer_id", "order_date", "status", "total_amount"],
        "order_items": ["order_item_id", "order_id", "product_id", "quantity", "unit_price"],
        "payments": ["payment_id", "order_id", "payment_date", "payment_method", "payment_status", "amount"],
    }
    for entity, data in rows.items():
        path = validated_dir / f"batch_id={batch_id}" / f"{entity}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(data, columns=header[entity]).to_csv(path, index=False)

    stage = run_spark_transform(batch_id, spark=spark)
    assert stage["output_counts"] == {
        "customers": 2, "products": 2, "orders": 2, "order_items": 3, "payments": 2
    }

    promote = promote_curated(batch_id)
    assert promote["report"]["engine"] == "pyspark"

    # Curated files exist in the V1 single-file layout, with loader columns.
    for entity, cols in CURATED_COLUMNS.items():
        f = curated_dir / f"batch_id={batch_id}" / entity / "data.parquet"
        assert f.exists(), f
        loaded = pd.read_parquet(f)
        assert list(loaded.columns) == cols
    orders = pd.read_parquet(curated_dir / f"batch_id={batch_id}" / "orders" / "data.parquet")
    assert orders.set_index("order_id").loc["O1", "total_amount_reconciled"] in (True, 1)
    assert bool(orders.set_index("order_id").loc["O2", "total_amount_reconciled"]) is False

    report = curated_dir / f"batch_id={batch_id}" / "transformation_report.json"
    assert report.exists()


def test_promote_refuses_when_curated_already_exists(spark, tmp_path, monkeypatch):
    from src.spark_transform.pipeline import SparkTransformError, promote_curated, run_spark_transform

    batch_id = "spark-it-0002"
    validated_dir = tmp_path / "validated"
    curated_dir = tmp_path / "curated"
    monkeypatch.setattr(settings, "DATA_VALIDATED_DIR", validated_dir)
    monkeypatch.setattr(settings, "DATA_CURATED_DIR", curated_dir)

    rows = _base_rows()
    header = {
        "customers": ["customer_id", "full_name", "email", "city", "state", "signup_date"],
        "products": ["product_id", "product_name", "category", "price"],
        "orders": ["order_id", "customer_id", "order_date", "status", "total_amount"],
        "order_items": ["order_item_id", "order_id", "product_id", "quantity", "unit_price"],
        "payments": ["payment_id", "order_id", "payment_date", "payment_method", "payment_status", "amount"],
    }
    for entity, data in rows.items():
        path = validated_dir / f"batch_id={batch_id}" / f"{entity}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(data, columns=header[entity]).to_csv(path, index=False)

    run_spark_transform(batch_id, spark=spark)
    promote_curated(batch_id)
    with pytest.raises(SparkTransformError):
        promote_curated(batch_id)
