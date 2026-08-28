"""QueryPilot — India Payments & Commerce Analytics dashboard.

A read-only presentation layer over the PostgreSQL warehouse this
project's pipeline builds (see README.md). It never writes to the
database and never re-runs ingestion/validation/transformation itself --
it only reads already-computed warehouse tables and, for pipeline-health
detail, already-written batch report files on disk.

The dataset is synthetic and generated locally with recent timestamps
(scripts/generate_dataset.py) -- it is presented as an operational
commerce/payments store, not described as a live or real-time feed. All
monetary values are Indian rupees (INR).

Run with:
    streamlit run dashboard/app.py
"""

import json
import logging
import sys
from pathlib import Path

# `streamlit run dashboard/app.py` (like `python dashboard/app.py`) executes
# this file directly, which puts only *this file's own directory* on
# sys.path[0] -- not the repository root. Without this, `from dashboard
# import queries` below fails with ModuleNotFoundError, since there is no
# `dashboard` package visible from inside dashboard/ itself; the imports
# from `src`/`config` elsewhere in this package would fail the same way.
# Must run before any of the project-local imports that follow.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd
import streamlit as st
from sqlalchemy.exc import OperationalError

from dashboard import charts, queries
from dashboard.components import (
    empty_state,
    inject_theme,
    kpi_row,
    lineage_badge,
    page_header,
    section_header,
)
from dashboard.db import get_engine
from dashboard.format import format_count, format_inr, format_inr_compact, format_percent
from dashboard.nl2sql_ui import render_ask_querypilot
from src.validation.rejection import rejected_batch_dir

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="QueryPilot — India Payments & Commerce Analytics", layout="wide")


def _get_connected_engine():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return engine
    except OperationalError as exc:
        logger.error("Dashboard could not connect to PostgreSQL: %s", exc)
        st.error(
            "Could not connect to PostgreSQL. Check POSTGRES_HOST / POSTGRES_PORT / "
            "POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB in your `.env` file and "
            "confirm the server is running and reachable."
        )
        st.stop()


def _safe(label: str, func, *args, **kwargs):
    """Runs a query function, logging the real exception server-side and
    showing only a generic message in the UI -- never a raw DB exception,
    which could describe internal connection details."""
    try:
        return func(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - deliberately broad: any query can fail
        logger.error("Dashboard query '%s' failed: %s", label, exc)
        st.error(f"Could not load '{label}'. See server logs for details.")
        return None


def _render_overview(engine, revenue, aov, payment_rate, reconciliation) -> None:
    section_header("Key metrics", "Current warehouse state · all amounts in INR")
    if None not in (revenue, aov, payment_rate, reconciliation):
        kpi_row(
            [
                ("Collected revenue", format_inr_compact(revenue), "Sum of successful payments (INR)"),
                ("Orders", format_count(aov["order_count"]), None),
                ("Average order value", format_inr_compact(aov["average_order_value"]), None),
                ("Payment success rate", format_percent(payment_rate), "Share of payments with status SUCCESS"),
                (
                    "Reconciliation rate",
                    format_percent(reconciliation["reconciliation_rate_pct"]),
                    "Share of orders whose recorded total matches the sum of their order_items",
                ),
            ]
        )

    st.write("")
    left, right = st.columns([3, 2])
    with left:
        section_header("Revenue trend", "Collected INR revenue by month")
        monthly = _safe("revenue by month", queries.revenue_by_month, engine)
        if monthly is not None:
            if monthly.empty:
                empty_state("No revenue recorded yet.")
            else:
                st.altair_chart(charts.revenue_trend(monthly), use_container_width=True)
    with right:
        section_header("Revenue by category", "Kept revenue, cancelled/returned excluded")
        by_category = _safe("revenue by category", queries.revenue_by_category, engine)
        if by_category is not None:
            if by_category.empty:
                empty_state("No category revenue yet.")
            else:
                st.altair_chart(
                    charts.magnitude_bar(by_category, category="category", value="revenue", height=300),
                    use_container_width=True,
                )


def _render_revenue(engine) -> None:
    section_header("Revenue by state", "Collected INR revenue attributed to the customer's home state")
    by_state = _safe("revenue by state", queries.revenue_by_state, engine)
    if by_state is not None:
        if by_state.empty:
            empty_state("No state-level revenue yet.")
        else:
            top_state = by_state.head(12)
            st.altair_chart(
                charts.magnitude_bar(
                    top_state, category="state", value="revenue", category_title=None, height=380
                ),
                use_container_width=True,
            )
            display = by_state.rename(
                columns={
                    "state": "State",
                    "revenue": "Collected revenue",
                    "paying_customers": "Paying customers",
                    "successful_payments": "Successful payments",
                }
            )
            display["Collected revenue"] = display["Collected revenue"].map(format_inr)
            display["Paying customers"] = display["Paying customers"].map(format_count)
            display["Successful payments"] = display["Successful payments"].map(format_count)
            with st.expander("All states"):
                st.dataframe(display, width="stretch", hide_index=True)

    st.write("")
    section_header("Monthly detail")
    monthly = _safe("revenue by month", queries.revenue_by_month, engine)
    if monthly is not None and not monthly.empty:
        detail = monthly.rename(
            columns={"month": "Month", "revenue": "Collected revenue", "successful_payments": "Successful payments"}
        )
        detail["Month"] = pd.to_datetime(detail["Month"]).dt.strftime("%b %Y")
        detail["Collected revenue"] = detail["Collected revenue"].map(format_inr)
        detail["Successful payments"] = detail["Successful payments"].map(format_count)
        st.dataframe(detail.iloc[::-1], width="stretch", hide_index=True)


def _render_customers(engine) -> None:
    section_header("Top customers", "By collected revenue from successful payments")
    top = _safe("top customers", queries.top_customers, engine)
    if top is not None:
        if top.empty:
            empty_state("No customer revenue yet.")
        else:
            display = top.rename(
                columns={
                    "customer_id": "Customer ID",
                    "full_name": "Name",
                    "city": "City",
                    "state": "State",
                    "revenue": "Collected revenue",
                    "successful_payments": "Successful payments",
                }
            )
            display["Collected revenue"] = display["Collected revenue"].map(format_inr)
            st.dataframe(display, width="stretch", hide_index=True)


def _render_orders_payments(engine) -> None:
    section_header("Order status", "Distribution of orders across the fulfilment lifecycle")
    status_df = _safe("order status distribution", queries.order_status_distribution, engine)
    if status_df is not None:
        if status_df.empty:
            empty_state("No order data yet.")
        else:
            st.altair_chart(
                charts.status_bar(
                    status_df, category="status", value="order_count", role_map=charts.ORDER_STATUS_ROLE
                ),
                use_container_width=True,
            )

    st.write("")
    col1, col2 = st.columns(2)
    with col1:
        section_header("Payment methods", "How customers pay — UPI-led, as in the Indian market")
        pay_method = _safe("payment method distribution", queries.payment_method_distribution, engine)
        if pay_method is not None and not pay_method.empty:
            st.altair_chart(
                charts.magnitude_bar(
                    pay_method, category="payment_method", value="payment_count", money=False, height=260
                ),
                use_container_width=True,
            )
    with col2:
        section_header("Payment status", "Outcome of every recorded payment attempt")
        pay_status = _safe("payment status distribution", queries.payment_status_distribution, engine)
        if pay_status is not None and not pay_status.empty:
            st.altair_chart(
                charts.status_bar(
                    pay_status,
                    category="payment_status",
                    value="payment_count",
                    role_map=charts.PAYMENT_STATUS_ROLE,
                ),
                use_container_width=True,
            )


def _render_data_quality(engine, batches) -> None:
    section_header(
        "Pipeline health",
        "The warehouse is current-state (Type 1): analytics elsewhere always reflect the latest "
        "successful load. The selector below only inspects one load's own lineage and quality report.",
    )
    successful_batches = batches[batches["status"] == "SUCCESS"]
    if successful_batches.empty:
        st.warning(
            "No successfully loaded batches found in `pipeline_batches`. Run the pipeline "
            "(ingestion → validation → transformation → warehouse) at least once, then reload."
        )
        return

    selected_batch_id = st.selectbox("Inspect a load", successful_batches["batch_id"])
    batch_row = batches[batches["batch_id"] == selected_batch_id].iloc[0]
    health_cols = st.columns(4)
    health_cols[0].metric("Status", batch_row["status"])
    health_cols[1].metric("Loaded rows", format_count(batch_row["loaded_row_count"] or 0))
    health_cols[2].metric("Curated rows", format_count(batch_row["curated_row_count"] or 0))
    health_cols[3].metric(
        "Loaded at", str(batch_row["completed_at"])[:19] if pd.notna(batch_row["completed_at"]) else "—"
    )

    quality_report_path = rejected_batch_dir(selected_batch_id) / "quality_report.json"
    if quality_report_path.exists():
        try:
            report = json.loads(quality_report_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Could not read quality report for %s: %s", selected_batch_id, exc)
            report = None
        if report is not None:
            st.write("")
            section_header("Validation quality report", f"Load {selected_batch_id}")
            qc1, qc2, qc3 = st.columns(3)
            qc1.metric("Valid rows", format_count(report["valid_rows"]))
            qc2.metric("Rejected rows", format_count(report["rejected_rows"]))
            qc3.metric("Quality", format_percent(report["quality_percentage"]))
            if report["rejection_reasons"]:
                with st.expander("Rejection reasons"):
                    reasons_df = pd.DataFrame(
                        sorted(report["rejection_reasons"].items(), key=lambda kv: -kv[1]),
                        columns=["Reason code", "Count"],
                    )
                    st.dataframe(reasons_df, width="stretch", hide_index=True)
    else:
        st.caption(
            "No validation quality report found on disk for this load "
            f"(expected under `data/rejected/batch_id={selected_batch_id}/`)."
        )

    with st.expander("All pipeline loads"):
        st.dataframe(batches, width="stretch", hide_index=True)

    st.write("")
    section_header(
        "Reconciliation mismatches",
        "Orders whose recorded total doesn't match the sum of their order_items, largest gap first.",
    )
    mismatches = _safe("reconciliation mismatches", queries.reconciliation_mismatches, engine)
    if mismatches is not None:
        if mismatches.empty:
            st.success("No reconciliation mismatches — every order's total matches its order_items.")
        else:
            display = mismatches.rename(
                columns={
                    "order_id": "Order ID",
                    "customer_id": "Customer ID",
                    "order_date": "Order date",
                    "source_total_amount": "Recorded total",
                    "calculated_total_amount": "Calculated total",
                    "total_amount_difference": "Difference",
                }
            )
            for col in ("Recorded total", "Calculated total", "Difference"):
                display[col] = display[col].map(format_inr)
            st.dataframe(display, width="stretch", hide_index=True)


def main() -> None:
    engine = _get_connected_engine()
    inject_theme()

    freshness = _safe("data freshness", queries.data_freshness, engine)
    as_of = ""
    if freshness and freshness.get("latest_order_date") is not None:
        as_of = f" · data as of {pd.to_datetime(freshness['latest_order_date']).strftime('%d %b %Y')}"

    page_header(
        "QueryPilot",
        "India Payments & Commerce Analytics",
        "Read-only analytics over a synthetic Indian digital-commerce warehouse "
        f"built by the ingestion → validation → transformation → warehouse pipeline.{as_of}",
    )
    lineage_badge("Warehouse")

    batches = _safe("pipeline batches", queries.pipeline_batches, engine)
    if batches is None:
        st.stop()
    if batches[batches["status"] == "SUCCESS"].empty:
        st.warning(
            "No successfully loaded batches found in `pipeline_batches`. Run the pipeline "
            "(ingestion → validation → transformation → warehouse) at least once, then reload this page."
        )
        st.stop()

    revenue = _safe("total revenue", queries.total_revenue, engine)
    aov = _safe("average order value", queries.average_order_value, engine)
    payment_rate = _safe("successful payment rate", queries.successful_payment_rate, engine)
    reconciliation = _safe("reconciliation rate", queries.order_reconciliation_rate, engine)

    overview, revenue_tab, customers_tab, ops_tab, quality_tab, ask_tab = st.tabs(
        ["Overview", "Revenue", "Customers", "Orders & Payments", "Data Quality", "Ask QueryPilot"]
    )
    with overview:
        _render_overview(engine, revenue, aov, payment_rate, reconciliation)
    with revenue_tab:
        _render_revenue(engine)
    with customers_tab:
        _render_customers(engine)
    with ops_tab:
        _render_orders_payments(engine)
    with quality_tab:
        _render_data_quality(engine, batches)
    with ask_tab:
        _safe("Ask QueryPilot", render_ask_querypilot, engine)


if __name__ == "__main__":
    main()
