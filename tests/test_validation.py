"""Tests for the data-quality / validation pipeline.

Rule-level tests exercise validate_* directly against small, hand-built
DataFrames -- no filesystem involved. Pipeline-level tests use isolated
tmp_path fixtures and monkeypatch `config.settings.DATA_RAW_DIR` /
`DATA_REJECTED_DIR`. None of this depends on the full generated dataset or
its 392 real defects.
"""

import pandas as pd
import pytest

from config import settings
from src.ingestion.schemas import EXPECTED_COLUMNS
from src.validation.pipeline import run_validation
from src.validation.reader import ValidationInputError
from src.validation.rejection import rejected_batch_dir
from src.validation.rules import (
    validate_customers,
    validate_order_items,
    validate_orders,
    validate_payments,
    validate_products,
)


def _df(rows, entity):
    return pd.DataFrame(rows, columns=EXPECTED_COLUMNS[entity])


def _customer(**overrides):
    row = {
        "customer_id": "C1",
        "full_name": "Alice",
        "email": "alice@example.com",
        "city": "Pune",
        "state": "Maharashtra",
        "signup_date": "2024-01-01",
    }
    row.update(overrides)
    return row


def _order(**overrides):
    row = {
        "order_id": "O1",
        "customer_id": "C1",
        "order_date": "2024-02-01",
        "status": "PLACED",
        "total_amount": "19.98",
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# Rule-level tests
# ---------------------------------------------------------------------------


def test_required_field_missing_is_flagged():
    df = _df([_customer(full_name="")], "customers")
    violations = validate_customers(df)
    assert any(v["code"] == "MISSING_FULL_NAME" for v in violations[0])


def test_duplicate_primary_key_flagged_on_both_rows():
    df = _df([_customer(customer_id="C1"), _customer(customer_id="C1", email="other@example.com")], "customers")
    violations = validate_customers(df)
    assert 0 in violations and 1 in violations
    assert all(any(v["code"] == "DUPLICATE_CUSTOMER_ID" for v in violations[i]) for i in (0, 1))


def test_invalid_foreign_key_flagged():
    customers = _df([_customer()], "customers")
    orders = _df([_order(customer_id="C999")], "orders")
    violations = validate_orders(orders, customers)
    assert any(v["code"] == "INVALID_CUSTOMER_FK" for v in violations[0])


def test_invalid_enum_flagged():
    customers = _df([_customer()], "customers")
    orders = _df([_order(status="SHIPPING_SOON")], "orders")
    violations = validate_orders(orders, customers)
    assert any(v["code"] == "INVALID_ORDER_STATUS" for v in violations[0])


def test_invalid_numeric_value_flagged():
    orders = _df([_order()], "orders")
    products = _df([{"product_id": "P1", "product_name": "Widget", "category": "Gadgets", "price": "5.0"}], "products")
    order_items = _df(
        [{"order_item_id": "OI1", "order_id": "O1", "product_id": "P1", "quantity": "-2", "unit_price": "5.0"}],
        "order_items",
    )
    violations = validate_order_items(order_items, orders, products)
    assert any(v["code"] == "INVALID_QUANTITY" for v in violations[0])


def test_invalid_date_flagged():
    df = _df([_customer(signup_date="not-a-date")], "customers")
    violations = validate_customers(df)
    assert any(v["code"] == "INVALID_SIGNUP_DATE" for v in violations[0])


def test_future_date_flagged():
    df = _df([_customer(signup_date="2099-01-01")], "customers")
    violations = validate_customers(df)
    assert any(v["code"] == "FUTURE_SIGNUP_DATE" for v in violations[0])


def test_temporal_ordering_order_before_signup_flagged():
    customers = _df([_customer(signup_date="2024-06-01")], "customers")
    orders = _df([_order(order_date="2024-01-01")], "orders")
    violations = validate_orders(orders, customers)
    assert any(v["code"] == "ORDER_DATE_BEFORE_CUSTOMER_SIGNUP" for v in violations[0])


def test_temporal_ordering_payment_before_order_flagged():
    orders = _df([_order(order_date="2024-06-01")], "orders")
    payments = _df(
        [
            {
                "payment_id": "PAY1",
                "order_id": "O1",
                "payment_date": "2024-01-01",
                "payment_method": "CREDIT_CARD",
                "payment_status": "SUCCESS",
                "amount": "19.98",
            }
        ],
        "payments",
    )
    violations = validate_payments(payments, orders)
    assert any(v["code"] == "PAYMENT_DATE_BEFORE_ORDER_DATE" for v in violations[0])


def test_multiple_reasons_preserved_on_one_row():
    customers = _df([], "customers")
    orders = _df(
        [_order(order_id="", customer_id="C999", order_date="bad-date", status="UNKNOWN", total_amount="-5")],
        "orders",
    )
    violations = validate_orders(orders, customers)
    codes = {v["code"] for v in violations[0]}
    assert {
        "MISSING_ORDER_ID",
        "INVALID_CUSTOMER_FK",
        "INVALID_ORDER_DATE",
        "INVALID_ORDER_STATUS",
        "NEGATIVE_TOTAL_AMOUNT",
    } <= codes


def test_clean_row_is_accepted():
    customers = _df([_customer()], "customers")
    orders = _df([_order()], "orders")
    assert validate_orders(orders, customers) == {}


# ---------------------------------------------------------------------------
# Pipeline-level tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_dirs(tmp_path, monkeypatch):
    raw_dir = tmp_path / "data" / "raw"
    rejected_dir = tmp_path / "data" / "rejected"
    validated_dir = tmp_path / "data" / "validated"
    monkeypatch.setattr(settings, "DATA_RAW_DIR", raw_dir)
    monkeypatch.setattr(settings, "DATA_REJECTED_DIR", rejected_dir)
    monkeypatch.setattr(settings, "DATA_VALIDATED_DIR", validated_dir)
    return raw_dir, rejected_dir


def _write_batch(raw_dir, batch_id, entity_frames):
    for entity, df in entity_frames.items():
        path = raw_dir / entity / f"batch_id={batch_id}" / f"{entity}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)


def _minimal_batch_with_one_bad_order():
    customers = _df([_customer()], "customers")
    products = _df([{"product_id": "P1", "product_name": "Widget", "category": "Gadgets", "price": "9.99"}], "products")
    orders = _df(
        [
            _order(order_id="O1"),
            _order(order_id="O2", customer_id="C999", total_amount="5.0"),  # invalid FK
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


def test_missing_batch_fails_clearly():
    with pytest.raises(ValidationInputError):
        run_validation("nonexistent-batch")


def test_end_to_end_writes_rejected_and_report(isolated_dirs):
    raw_dir, rejected_dir = isolated_dirs
    batch_id = "batchXYZ"
    _write_batch(raw_dir, batch_id, _minimal_batch_with_one_bad_order())

    report = run_validation(batch_id)

    assert report["batch_id"] == batch_id
    assert report["total_rows"] == 1 + 1 + 2 + 1 + 1
    assert report["rejected_rows"] == 1
    assert report["entities"]["orders"]["rejected_rows"] == 1
    assert "INVALID_CUSTOMER_FK" in report["rejection_reasons"]

    batch_dir = rejected_dir / f"batch_id={batch_id}"
    assert (batch_dir / "quality_report.json").exists()
    assert (batch_dir / "orders.csv").exists()
    # Entities with zero rejects get no output file.
    assert not (batch_dir / "customers.csv").exists()
    assert not (batch_dir / "products.csv").exists()


def test_order_referencing_a_rejected_customer_is_itself_rejected(isolated_dirs):
    """Regression test: a customer_id that exists in the raw file but was
    itself rejected (e.g. a duplicate PK) must not count as a valid FK
    target -- an order referencing it has to be rejected too, not merely
    accepted because the raw id happened to appear somewhere."""
    raw_dir, rejected_dir = isolated_dirs
    batch_id = "batchDangling"
    customers = _df(
        [_customer(customer_id="C1"), _customer(customer_id="C1", email="other@example.com")],  # duplicate PK
        "customers",
    )
    orders = _df(
        [_order(order_id="O1", customer_id="C1"), _order(order_id="O2", customer_id="C1")],
        "orders",
    )  # both reference the rejected C1
    products = _df([{"product_id": "P1", "product_name": "Widget", "category": "Gadgets", "price": "9.99"}], "products")
    order_items = _df(
        [{"order_item_id": "OI1", "order_id": "O2", "product_id": "P1", "quantity": "1", "unit_price": "9.99"}],
        "order_items",
    )
    payments = _df(
        [
            {
                "payment_id": "PAY1",
                "order_id": "O2",
                "payment_date": "2024-02-02",
                "payment_method": "CREDIT_CARD",
                "payment_status": "SUCCESS",
                "amount": "9.99",
            }
        ],
        "payments",
    )
    _write_batch(
        raw_dir,
        batch_id,
        {
            "customers": customers,
            "orders": orders,
            "products": products,
            "order_items": order_items,
            "payments": payments,
        },
    )

    report = run_validation(batch_id)

    assert report["entities"]["customers"]["rejected_rows"] == 2  # both sides of the duplicate
    assert report["entities"]["orders"]["rejected_rows"] == 2  # O1 and O2 both reference invalid C1
    assert "INVALID_CUSTOMER_FK" in report["rejection_reasons"]

    # The cascade goes one level further: O2 is itself rejected, so
    # order_items/payments referencing O2 must be rejected too.
    assert report["entities"]["order_items"]["rejected_rows"] == 1
    assert report["entities"]["payments"]["rejected_rows"] == 1
    assert "INVALID_ORDER_FK" in report["rejection_reasons"]

    orders_rejected = (rejected_dir / f"batch_id={batch_id}" / "orders.csv").read_text()
    assert "INVALID_CUSTOMER_FK" in orders_rejected


def test_rerunning_same_batch_fails_clearly_and_does_not_overwrite(isolated_dirs):
    raw_dir, rejected_dir = isolated_dirs
    batch_id = "batchXYZ"
    _write_batch(raw_dir, batch_id, _minimal_batch_with_one_bad_order())

    first_report = run_validation(batch_id)
    report_file = rejected_dir / f"batch_id={batch_id}" / "quality_report.json"
    original_contents = report_file.read_text()

    with pytest.raises(ValidationInputError):
        run_validation(batch_id)

    assert report_file.read_text() == original_contents
    assert first_report["rejected_rows"] == 1
