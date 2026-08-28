"""Read-only query execution for the dashboard.

sql/analytics/*.sql is the single source of truth: every query here is
read from those files and executed as-is, never re-typed as a Python
string. The one dashboard-specific query (pipeline batch history) lives
under sql/analytics/dashboard/, for the same reason.

Each function that returns a DataFrame is Streamlit-cached (short TTL) so
navigating the dashboard doesn't re-hit PostgreSQL for the same KPI on
every rerun. The `_engine` parameter name (leading underscore) is
Streamlit's convention for "don't try to hash this argument".
"""

from functools import lru_cache
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy.engine import Engine

from config import settings

ANALYTICS_DIR = settings.PROJECT_ROOT / "sql" / "analytics"
DASHBOARD_QUERIES_DIR = ANALYTICS_DIR / "dashboard"

_CACHE_TTL_SECONDS = 60


@lru_cache(maxsize=None)
def _load_sql(path: Path) -> str:
    return path.read_text()


def _run(engine: Engine, path: Path) -> pd.DataFrame:
    return pd.read_sql(_load_sql(path), engine)


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def total_revenue(_engine: Engine) -> float:
    df = _run(_engine, ANALYTICS_DIR / "01_total_revenue.sql")
    value = df["total_revenue"].iloc[0]
    return float(value) if value is not None else 0.0


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def revenue_by_month(_engine: Engine) -> pd.DataFrame:
    return _run(_engine, ANALYTICS_DIR / "02_revenue_by_month.sql")


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def revenue_by_category(_engine: Engine) -> pd.DataFrame:
    return _run(_engine, ANALYTICS_DIR / "03_revenue_by_category.sql")


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def top_customers(_engine: Engine) -> pd.DataFrame:
    return _run(_engine, ANALYTICS_DIR / "04_top_customers_by_revenue.sql")


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def revenue_by_state(_engine: Engine) -> pd.DataFrame:
    return _run(_engine, ANALYTICS_DIR / "11_revenue_by_state.sql")


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def average_order_value(_engine: Engine) -> dict:
    df = _run(_engine, ANALYTICS_DIR / "05_average_order_value.sql")
    row = df.iloc[0]
    return {
        "average_order_value": float(row["average_order_value"] or 0),
        "order_count": int(row["order_count"]),
    }


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def order_status_distribution(_engine: Engine) -> pd.DataFrame:
    return _run(_engine, ANALYTICS_DIR / "06_order_status_distribution.sql")


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def payment_method_distribution(_engine: Engine) -> pd.DataFrame:
    return _run(_engine, ANALYTICS_DIR / "07_payment_method_distribution.sql")


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def payment_status_distribution(_engine: Engine) -> pd.DataFrame:
    return _run(_engine, ANALYTICS_DIR / "08_payment_status_distribution.sql")


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def order_reconciliation_rate(_engine: Engine) -> dict:
    df = _run(_engine, ANALYTICS_DIR / "09_order_reconciliation_rate.sql")
    row = df.iloc[0]
    return {
        "total_orders": int(row["total_orders"]),
        "reconciled_orders": int(row["reconciled_orders"]),
        "non_reconciled_orders": int(row["non_reconciled_orders"]),
        "reconciliation_rate_pct": float(row["reconciliation_rate_pct"] or 0),
    }


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def reconciliation_mismatches(_engine: Engine) -> pd.DataFrame:
    return _run(_engine, ANALYTICS_DIR / "10_orders_with_reconciliation_mismatches.sql")


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def pipeline_batches(_engine: Engine) -> pd.DataFrame:
    return _run(_engine, DASHBOARD_QUERIES_DIR / "pipeline_batches_summary.sql")


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def data_freshness(_engine: Engine) -> dict:
    df = _run(_engine, DASHBOARD_QUERIES_DIR / "data_freshness.sql")
    row = df.iloc[0]
    return {
        "latest_order_date": row["latest_order_date"],
        "latest_payment_date": row["latest_payment_date"],
    }


def successful_payment_rate(engine: Engine) -> float:
    """Derived from payment_status_distribution rather than a new query."""
    df = payment_status_distribution(engine)
    success = df[df["payment_status"] == "SUCCESS"]
    if success.empty:
        return 0.0
    return float(success["pct_of_payments"].iloc[0])
