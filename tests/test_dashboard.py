"""Tests for the dashboard's read-only query layer.

Uses the shared `engine` fixture from conftest.py -- a fresh, throwaway
PostgreSQL database created for this module and dropped afterward, never
the user's real POSTGRES_DB. Skips with a clear explanation if no
PostgreSQL server is reachable (see conftest.py's docstring).

These tests exercise dashboard/db.py and dashboard/queries.py directly --
the code the Streamlit app calls -- not the Streamlit UI itself. A full
UI test suite is explicitly out of scope for this phase.
"""

import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import text

from config import settings
from dashboard import queries
from dashboard.db import build_readonly_engine
from dashboard.format import (
    format_count,
    format_inr,
    format_inr_compact,
    format_percent,
    indian_grouping,
)
from src.transformation.writer import curated_entity_path
from src.warehouse.pipeline import run_warehouse_load
from src.warehouse.schema import apply_schema

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# INR / number formatting (dashboard/format.py) -- pure, no database.
# ---------------------------------------------------------------------------


def test_indian_grouping_places_commas_the_indian_way():
    assert indian_grouping("1250") == "1,250"
    assert indian_grouping("123456") == "1,23,456"
    assert indian_grouping("12345678") == "1,23,45,678"
    assert indian_grouping("999") == "999"


def test_format_inr_is_exact_with_symbol_and_grouping():
    assert format_inr(1250) == "₹1,250.00"
    assert format_inr(1234567.89) == "₹12,34,567.89"
    assert format_inr(0) == "₹0.00"
    assert format_inr(-500, decimals=0) == "-₹500"
    assert format_inr(None) == "—"


def test_format_inr_compact_scales_to_lakh_and_crore():
    assert format_inr_compact(950) == "₹950"
    assert format_inr_compact(45000) == "₹45,000"
    assert format_inr_compact(125000) == "₹1.25L"
    assert format_inr_compact(1240000) == "₹12.4L"
    assert format_inr_compact(12400000) == "₹1.24Cr"
    assert format_inr_compact(None) == "—"


def test_format_percent_and_count():
    assert format_percent(87.031) == "87.0%"
    assert format_percent(None) == "—"
    assert format_count(1833) == "1,833"
    assert format_count(None) == "—"


# ---------------------------------------------------------------------------
# Regression: dashboard/app.py must be importable exactly the way
# `streamlit run dashboard/app.py` runs it. No database needed.
# ---------------------------------------------------------------------------


def test_app_entrypoint_importable_via_streamlit_style_execution(engine):
    """`streamlit run dashboard/app.py` (like plain `python dashboard/app.py`)
    sets sys.path[0] to dashboard/'s own directory, not the repository
    root -- so `from dashboard import queries` (and the src./config.
    imports elsewhere in the file) failed with ModuleNotFoundError until
    app.py added the repo root to sys.path itself, before those imports.

    Must run in a genuine fresh subprocess invoked *by file path*, exactly
    as Streamlit invokes it -- not via `python -c`, which sets its own
    sys.path[0] to the current directory and would silently mask this
    exact bug (it did, the first time this test was written: `-c` made
    the repo root importable regardless of whether app.py's own fix was
    present). Also strips any inherited PYTHONPATH, since pytest's own
    `pythonpath = .` (pytest.ini) would mask the bug the same way if it
    leaked into the subprocess's environment.

    Takes the `engine` fixture only for its skip-if-Postgres-unreachable
    behavior, so this test doesn't hang/timeout in an environment with no
    database -- main() will attempt a real (read-only) connection using
    the real configured POSTGRES_DB, but the assertions below only check
    that the entrypoint *imports* cleanly, regardless of what happens
    with the database afterward.
    """
    del engine  # only requested to inherit the reachability skip-check

    app_path = REPO_ROOT / "dashboard" / "app.py"

    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [sys.executable, str(app_path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )

    combined_output = result.stdout + result.stderr
    assert "ModuleNotFoundError" not in combined_output, combined_output
    assert "ImportError" not in combined_output, combined_output


def _kpi_fixture_batch():
    """Two orders (one reconciled, one not) and two payments (one success,
    one failed) -- rich enough to make KPI assertions non-trivial, unlike
    the single-row fixture in test_warehouse.py."""
    customers = pd.DataFrame(
        [
            {"customer_id": "DC1", "full_name": "Dana Lee", "email": "dana@x.com", "city": "Bengaluru",
             "state": "Karnataka", "signup_date": pd.Timestamp("2024-01-01")},
        ]
    )
    products = pd.DataFrame(
        [{"product_id": "DP1", "product_name": "Widget", "category": "Gadgets", "price": 25.0}]
    )
    orders = pd.DataFrame(
        [
            {"order_id": "DO1", "customer_id": "DC1", "order_date": pd.Timestamp("2024-02-01"),
             "status": "DELIVERED", "source_total_amount": 50.0, "calculated_total_amount": 50.0,
             "total_amount_difference": 0.0, "total_amount_reconciled": True},
            {"order_id": "DO2", "customer_id": "DC1", "order_date": pd.Timestamp("2024-03-01"),
             "status": "PLACED", "source_total_amount": 200.0, "calculated_total_amount": 25.0,
             "total_amount_difference": 175.0, "total_amount_reconciled": False},
        ]
    )
    order_items = pd.DataFrame(
        [
            {"order_item_id": "DOI1", "order_id": "DO1", "product_id": "DP1", "quantity": 2, "unit_price": 25.0,
             "line_total": 50.0},
            {"order_item_id": "DOI2", "order_id": "DO2", "product_id": "DP1", "quantity": 1, "unit_price": 25.0,
             "line_total": 25.0},
        ]
    )
    payments = pd.DataFrame(
        [
            {"payment_id": "DPAY1", "order_id": "DO1", "payment_date": pd.Timestamp("2024-02-02"),
             "payment_method": "CREDIT_CARD", "payment_status": "SUCCESS", "amount": 50.0},
            {"payment_id": "DPAY2", "order_id": "DO2", "payment_date": pd.Timestamp("2024-03-02"),
             "payment_method": "UPI", "payment_status": "FAILED", "amount": 200.0},
        ]
    )
    return {
        "customers": customers,
        "products": products,
        "orders": orders,
        "order_items": order_items,
        "payments": payments,
    }


@pytest.fixture(scope="module")
def loaded_engine(engine):
    """The shared throwaway database, with the KPI fixture batch loaded
    into it once, reused read-only by every test in this module."""
    apply_schema(engine)
    batch_id = f"dashboard-test-{uuid.uuid4().hex[:8]}"

    original_curated_dir = settings.DATA_CURATED_DIR
    with tempfile.TemporaryDirectory() as tmp:
        settings.DATA_CURATED_DIR = Path(tmp) / "data" / "curated"
        try:
            for entity, df in _kpi_fixture_batch().items():
                path = curated_entity_path(entity, batch_id)
                path.parent.mkdir(parents=True, exist_ok=True)
                df.to_parquet(path)
            run_warehouse_load(batch_id, engine=engine)
        finally:
            settings.DATA_CURATED_DIR = original_curated_dir

    return engine


# ---------------------------------------------------------------------------
# 1. Database connectivity/configuration
# ---------------------------------------------------------------------------


def test_build_readonly_engine_connects(engine):
    readonly_engine = build_readonly_engine(database=engine.url.database)
    with readonly_engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1
    readonly_engine.dispose()


def test_readonly_engine_actually_rejects_writes(engine):
    readonly_engine = build_readonly_engine(database=engine.url.database)
    with pytest.raises(Exception):
        with readonly_engine.connect() as conn:
            conn.execute(text("CREATE TABLE should_never_be_created (id INT)"))
            conn.commit()
    readonly_engine.dispose()

    with engine.connect() as conn:
        exists = conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'should_never_be_created')"
            )
        ).scalar()
    assert exists is False


# ---------------------------------------------------------------------------
# 2 & 6. Analytical query execution + expected schema/columns
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("func_name", "expected_columns"),
    [
        ("revenue_by_month", {"month", "revenue", "successful_payments"}),
        ("revenue_by_category", {"category", "revenue", "order_count"}),
        ("top_customers", {"customer_id", "full_name", "city", "state", "revenue", "successful_payments"}),
        ("order_status_distribution", {"status", "order_count", "pct_of_orders"}),
        ("payment_method_distribution", {"payment_method", "payment_count", "pct_of_payments"}),
        ("payment_status_distribution", {"payment_status", "payment_count", "pct_of_payments"}),
        ("reconciliation_mismatches", {"order_id", "customer_id", "order_date", "source_total_amount",
                                        "calculated_total_amount", "total_amount_difference"}),
        ("pipeline_batches", {"batch_id", "status", "started_at", "completed_at",
                               "curated_row_count", "loaded_row_count", "error_message"}),
    ],
)
def test_query_returns_expected_columns(loaded_engine, func_name, expected_columns):
    func = getattr(queries, func_name)
    df = func(loaded_engine)
    assert expected_columns <= set(df.columns)


# ---------------------------------------------------------------------------
# 3. KPI query results
# ---------------------------------------------------------------------------


def test_total_revenue_kpi(loaded_engine):
    # Only DPAY1 (SUCCESS, 50.0) counts -- DPAY2 is FAILED.
    assert queries.total_revenue(loaded_engine) >= 50.0


def test_average_order_value_kpi(loaded_engine):
    result = queries.average_order_value(loaded_engine)
    assert result["order_count"] >= 2
    assert result["average_order_value"] > 0


def test_successful_payment_rate_kpi(loaded_engine):
    rate = queries.successful_payment_rate(loaded_engine)
    assert 0.0 <= rate <= 100.0


def test_reconciliation_rate_kpi(loaded_engine):
    result = queries.order_reconciliation_rate(loaded_engine)
    assert result["total_orders"] >= 2
    assert result["reconciled_orders"] >= 1
    assert result["non_reconciled_orders"] >= 1
    assert 0.0 <= result["reconciliation_rate_pct"] <= 100.0


# ---------------------------------------------------------------------------
# 4. Batch selection
# ---------------------------------------------------------------------------


def test_pipeline_batches_lists_successful_batch(loaded_engine):
    df = queries.pipeline_batches(loaded_engine)
    successful = df[df["status"] == "SUCCESS"]
    assert not successful.empty


# ---------------------------------------------------------------------------
# 5. Reconciliation query
# ---------------------------------------------------------------------------


def test_reconciliation_mismatches_includes_known_mismatch(loaded_engine):
    df = queries.reconciliation_mismatches(loaded_engine)
    assert "DO2" in df["order_id"].values
    row = df[df["order_id"] == "DO2"].iloc[0]
    assert float(row["total_amount_difference"]) == pytest.approx(175.0, abs=0.01)
    assert "DO1" not in df["order_id"].values  # DO1 is reconciled, must not appear
