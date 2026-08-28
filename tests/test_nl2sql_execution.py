"""Tests for the bounded, read-only SQL execution layer
(src/nl2sql/execution.py).

Uses the shared `engine` fixture from conftest.py -- a fresh, throwaway
PostgreSQL database created for this module and dropped afterward. See
conftest.py's docstring for what's required to run these tests.

Deliberately tests the execution boundary independently of the real
validator: most tests hand-construct a `SQLValidationResult` directly
(via `_valid()` / `_invalid()` below) rather than calling
`validate_sql()`, including a couple of adversarial ones that build a
`SQLValidationResult(is_valid=True, ...)` around a genuine write
statement -- simulating "validation said yes" to prove that
execute_sql's read-only guarantee is a second, independent boundary,
not something that only works because the validator already filtered
the input. A handful of tests do exercise the real generate-validate-
execute chain together to prove the pieces fit.
"""

import time
import uuid

import pandas as pd
import pytest

from src.nl2sql.execution import (
    DEFAULT_MAX_ROWS,
    SQLExecutionError,
    SQLExecutionResult,
    execute_sql,
)
from src.nl2sql.validation import SQLValidationResult, validate_sql
from src.warehouse.db import get_readonly_engine
from src.warehouse.pipeline import run_warehouse_load
from src.warehouse.schema import apply_schema
from tests.conftest import _write_curated_batch


def _valid(sql: str, tables=()) -> SQLValidationResult:
    return SQLValidationResult(is_valid=True, normalized_sql=sql, errors=(), referenced_tables=tuple(tables))


def _invalid(errors=("rejected",)) -> SQLValidationResult:
    return SQLValidationResult(is_valid=False, normalized_sql=None, errors=tuple(errors), referenced_tables=())


def _fixture_batch():
    customers = pd.DataFrame(
        [
            {"customer_id": "EC1", "full_name": "Alice", "email": "alice@x.com", "city": "Pune", "state": "Maharashtra",
             "signup_date": pd.Timestamp("2024-01-01")},
            {"customer_id": "EC2", "full_name": "Bob", "email": "bob@x.com", "city": "Delhi", "state": "Delhi",
             "signup_date": pd.Timestamp("2024-01-02")},
        ]
    )
    products = pd.DataFrame(
        [{"product_id": "EP1", "product_name": "Widget", "category": "Gadgets", "price": 10.0}]
    )
    orders = pd.DataFrame(
        [
            {"order_id": "EO1", "customer_id": "EC1", "order_date": pd.Timestamp("2024-02-01"),
             "status": "DELIVERED", "source_total_amount": 20.0, "calculated_total_amount": 20.0,
             "total_amount_difference": 0.0, "total_amount_reconciled": True},
            {"order_id": "EO2", "customer_id": "EC2", "order_date": pd.Timestamp("2024-02-02"),
             "status": "PLACED", "source_total_amount": 10.0, "calculated_total_amount": 10.0,
             "total_amount_difference": 0.0, "total_amount_reconciled": True},
        ]
    )
    order_items = pd.DataFrame(
        [
            {"order_item_id": "EOI1", "order_id": "EO1", "product_id": "EP1", "quantity": 2, "unit_price": 10.0,
             "line_total": 20.0},
            {"order_item_id": "EOI2", "order_id": "EO2", "product_id": "EP1", "quantity": 1, "unit_price": 10.0,
             "line_total": 10.0},
        ]
    )
    payments = pd.DataFrame(
        [
            {"payment_id": "EPAY1", "order_id": "EO1", "payment_date": pd.Timestamp("2024-02-02"),
             "payment_method": "CREDIT_CARD", "payment_status": "SUCCESS", "amount": 20.0},
            {"payment_id": "EPAY2", "order_id": "EO2", "payment_date": pd.Timestamp("2024-02-03"),
             "payment_method": "UPI", "payment_status": "SUCCESS", "amount": 10.0},
        ]
    )
    return {
        "customers": customers, "products": products, "orders": orders,
        "order_items": order_items, "payments": payments,
    }


@pytest.fixture(scope="module")
def loaded_readonly_engine(engine):
    """The shared throwaway database, with a small fixture batch loaded,
    exposed as a *read-only* engine pointed at that same database --
    mirrors how tests/test_dashboard.py builds its read-only test engine."""
    apply_schema(engine)
    batch_id = f"exec-test-{uuid.uuid4().hex[:8]}"
    import tempfile
    from pathlib import Path
    from config import settings

    original_curated_dir = settings.DATA_CURATED_DIR
    with tempfile.TemporaryDirectory() as tmp:
        settings.DATA_CURATED_DIR = Path(tmp) / "data" / "curated"
        try:
            for entity, df in _fixture_batch().items():
                from src.transformation.writer import curated_entity_path
                path = curated_entity_path(entity, batch_id)
                path.parent.mkdir(parents=True, exist_ok=True)
                df.to_parquet(path)
            run_warehouse_load(batch_id, engine=engine)
        finally:
            settings.DATA_CURATED_DIR = original_curated_dir

    readonly_engine = get_readonly_engine(database=engine.url.database)
    yield readonly_engine
    readonly_engine.dispose()


# ---------------------------------------------------------------------------
# 1. Type-level trust boundary -- misuse is rejected before any DB call
# ---------------------------------------------------------------------------


def test_rejects_a_raw_sql_string_instead_of_a_validation_result():
    with pytest.raises(SQLExecutionError):
        execute_sql("SELECT 1")  # not a SQLValidationResult at all


def test_rejects_a_failed_validation_result():
    with pytest.raises(SQLExecutionError):
        execute_sql(_invalid(["SELECT INTO is not allowed."]))


def test_rejects_invalid_max_rows():
    with pytest.raises(SQLExecutionError):
        execute_sql(_valid("SELECT 1"), max_rows=0)
    with pytest.raises(SQLExecutionError):
        execute_sql(_valid("SELECT 1"), max_rows=-5)


def test_rejects_invalid_timeout():
    with pytest.raises(SQLExecutionError):
        execute_sql(_valid("SELECT 1"), timeout_seconds=0)
    with pytest.raises(SQLExecutionError):
        execute_sql(_valid("SELECT 1"), timeout_seconds=-1)


# ---------------------------------------------------------------------------
# 2. Basic successful execution
# ---------------------------------------------------------------------------


def test_executes_a_simple_select(loaded_readonly_engine):
    result = execute_sql(_valid("SELECT 1 AS one"), engine=loaded_readonly_engine)
    assert isinstance(result, SQLExecutionResult)
    assert result.success is True
    assert result.error is None
    assert result.columns == ("one",)
    assert result.rows == ({"one": 1},)
    assert result.row_count == 1
    assert result.truncated is False
    assert result.elapsed_seconds >= 0


def test_executes_against_real_loaded_data(loaded_readonly_engine):
    result = execute_sql(
        _valid("SELECT customer_id, full_name FROM customers ORDER BY customer_id", tables=["customers"]),
        engine=loaded_readonly_engine,
    )
    assert result.success is True
    assert result.row_count == 2
    assert result.rows[0]["customer_id"] == "EC1"
    assert result.rows[1]["customer_id"] == "EC2"


def test_generate_validate_execute_chain_fits_together(loaded_readonly_engine):
    """Not a real LLM call -- simulates SQLGenerationResult.sql with a
    plain string to prove validate_sql()'s output is exactly what
    execute_sql() expects, with no glue code needed in between."""
    candidate_sql = "SELECT category, SUM(price) AS total FROM products GROUP BY category"
    validation = validate_sql(candidate_sql)
    assert validation.is_valid

    result = execute_sql(validation, engine=loaded_readonly_engine)
    assert result.success is True
    assert result.rows == ({"category": "Gadgets", "total": 10.0},)


# ---------------------------------------------------------------------------
# 3. Row cap
# ---------------------------------------------------------------------------


def test_row_cap_truncates_and_flags_truncated(loaded_readonly_engine):
    result = execute_sql(_valid("SELECT generate_series(1, 10) AS n"), engine=loaded_readonly_engine, max_rows=5)
    assert result.success is True
    assert result.row_count == 5
    assert result.truncated is True


def test_row_cap_not_flagged_when_result_fits(loaded_readonly_engine):
    result = execute_sql(_valid("SELECT generate_series(1, 3) AS n"), engine=loaded_readonly_engine, max_rows=5)
    assert result.success is True
    assert result.row_count == 3
    assert result.truncated is False


def test_default_max_rows_is_a_sane_positive_number():
    assert isinstance(DEFAULT_MAX_ROWS, int)
    assert DEFAULT_MAX_ROWS > 0


# ---------------------------------------------------------------------------
# 4. Timeout enforcement
# ---------------------------------------------------------------------------


def test_statement_timeout_cancels_a_slow_query_and_reports_failure(loaded_readonly_engine):
    start = time.monotonic()
    result = execute_sql(_valid("SELECT pg_sleep(5)"), engine=loaded_readonly_engine, timeout_seconds=0.5)
    elapsed = time.monotonic() - start

    assert result.success is False
    assert result.error is not None
    assert "timeout" in result.error.lower() or "cancel" in result.error.lower()
    assert elapsed < 4.0  # cancelled well before pg_sleep(5) would have finished


def test_connection_is_still_usable_after_a_timeout(loaded_readonly_engine):
    execute_sql(_valid("SELECT pg_sleep(2)"), engine=loaded_readonly_engine, timeout_seconds=0.3)
    result = execute_sql(_valid("SELECT 1"), engine=loaded_readonly_engine)
    assert result.success is True


# ---------------------------------------------------------------------------
# 5. Read-only guarantee is a second, independent boundary
# ---------------------------------------------------------------------------


def test_read_only_session_blocks_a_write_even_if_a_validation_result_claims_it_is_valid(loaded_readonly_engine):
    """Simulates a bug or gap in validate_sql() by hand-building an
    is_valid=True result around a genuine DELETE. execute_sql() does not
    re-inspect the SQL text -- the read-only DB session itself must be
    what stops this, proving the guarantee doesn't depend on validation
    having done its job correctly."""
    result = execute_sql(_valid("DELETE FROM customers WHERE customer_id = 'EC1'"), engine=loaded_readonly_engine)
    assert result.success is False
    assert result.error is not None

    # And the row is still there.
    check = execute_sql(_valid("SELECT customer_id FROM customers WHERE customer_id = 'EC1'"), engine=loaded_readonly_engine)
    assert check.success is True
    assert check.row_count == 1


def test_read_only_session_blocks_ddl_too(loaded_readonly_engine):
    result = execute_sql(_valid("CREATE TABLE should_never_exist (id INT)"), engine=loaded_readonly_engine)
    assert result.success is False


# ---------------------------------------------------------------------------
# 6. Runtime SQL errors are reported, not raised
# ---------------------------------------------------------------------------


def test_runtime_sql_error_is_reported_as_a_failed_result_not_an_exception(loaded_readonly_engine):
    """A statement that passed static validation can still fail at
    execution time (e.g. a column that doesn't exist) -- this should
    come back as a normal failed SQLExecutionResult, not blow up the
    caller."""
    result = execute_sql(_valid("SELECT this_column_does_not_exist FROM customers"), engine=loaded_readonly_engine)
    assert result.success is False
    assert result.error is not None
    assert result.rows == ()
