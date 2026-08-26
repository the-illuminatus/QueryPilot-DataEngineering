"""QueryPilot — Data Engineering Analytics dashboard.

A read-only presentation layer over the PostgreSQL warehouse this
project's pipeline builds (see README.md). It never writes to the
database and never re-runs ingestion/validation/transformation itself --
it only reads already-computed warehouse tables and, for pipeline-health
detail, already-written batch report files on disk.

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

from dashboard import queries
from dashboard.components import format_currency, format_percent, kpi_row, lineage_badge, section_header
from dashboard.db import get_engine
from src.validation.rejection import rejected_batch_dir

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="QueryPilot — Data Engineering Analytics", layout="wide")


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


def main() -> None:
    engine = _get_connected_engine()

    # --- A. Header ---------------------------------------------------------
    st.title("QueryPilot — Data Engineering Analytics")
    st.caption(
        "Read-only dashboard over the PostgreSQL warehouse produced by the "
        "ingestion → validation → transformation → warehouse pipeline."
    )
    lineage_badge("Warehouse")

    batches = _safe("pipeline batches", queries.pipeline_batches, engine)
    if batches is None:
        st.stop()

    successful_batches = batches[batches["status"] == "SUCCESS"]
    if successful_batches.empty:
        st.warning(
            "No successfully loaded batches found in `pipeline_batches`. Run the "
            "pipeline (ingestion → validation → transformation → warehouse) at "
            "least once, then reload this page."
        )
        st.stop()

    st.info(
        "This warehouse uses a current-state (Type 1) design: `customers` / "
        "`orders` / etc. always reflect the *latest successful load*, not a "
        "historical snapshot per batch. The selector below only inspects that "
        "one load's own lineage and health (section **G**) — every analytics "
        "figure elsewhere on this page reflects the current warehouse state, "
        "not the selected batch."
    )
    selected_batch_id = st.selectbox(
        "Inspect a load (lineage/health only)",
        successful_batches["batch_id"],
    )

    st.divider()

    # --- B. KPI section ------------------------------------------------------
    section_header("Key Metrics")
    revenue = _safe("total revenue", queries.total_revenue, engine)
    aov = _safe("average order value", queries.average_order_value, engine)
    payment_rate = _safe("successful payment rate", queries.successful_payment_rate, engine)
    reconciliation = _safe("reconciliation rate", queries.order_reconciliation_rate, engine)

    if None not in (revenue, aov, payment_rate, reconciliation):
        kpi_row(
            [
                ("Total Revenue", format_currency(revenue), "Sum of successful payments"),
                ("Total Orders", f"{aov['order_count']:,}", None),
                ("Average Order Value", format_currency(aov["average_order_value"]), None),
                ("Successful Payment Rate", format_percent(payment_rate), None),
                (
                    "Reconciliation Rate",
                    format_percent(reconciliation["reconciliation_rate_pct"]),
                    "Share of orders whose recorded total matches the sum of their order_items",
                ),
            ]
        )

    st.divider()

    # --- C. Revenue analytics -------------------------------------------------
    section_header("Revenue Analytics")
    col1, col2 = st.columns(2)
    with col1:
        st.caption("Revenue by Month")
        monthly = _safe("revenue by month", queries.revenue_by_month, engine)
        if monthly is not None:
            if monthly.empty:
                st.info("No revenue data available yet.")
            else:
                st.line_chart(monthly.set_index("month")["revenue"])
    with col2:
        st.caption("Revenue by Product Category")
        by_category = _safe("revenue by category", queries.revenue_by_category, engine)
        if by_category is not None:
            if by_category.empty:
                st.info("No category revenue data available yet.")
            else:
                st.bar_chart(by_category.set_index("category")["revenue"])

    st.divider()

    # --- D. Customer analytics -------------------------------------------------
    section_header("Top Customers", "By revenue from successful payments")
    top = _safe("top customers", queries.top_customers, engine)
    if top is not None:
        if top.empty:
            st.info("No customer revenue data available yet.")
        else:
            display = top.rename(
                columns={
                    "customer_id": "Customer ID",
                    "full_name": "Name",
                    "country": "Country",
                    "revenue": "Revenue",
                    "successful_payments": "Successful Payments",
                }
            )
            display["Revenue"] = display["Revenue"].map(format_currency)
            st.dataframe(display, use_container_width=True, hide_index=True)

    st.divider()

    # --- E. Order analytics -------------------------------------------------
    section_header("Order Analytics")
    col1, col2 = st.columns([2, 1])
    with col1:
        st.caption("Order Status Distribution")
        status_df = _safe("order status distribution", queries.order_status_distribution, engine)
        if status_df is not None:
            if status_df.empty:
                st.info("No order data available yet.")
            else:
                st.bar_chart(status_df.set_index("status")["order_count"])
    with col2:
        if aov is not None:
            st.metric("Average Order Value", format_currency(aov["average_order_value"]))
        if reconciliation is not None:
            st.metric(
                "Reconciliation Rate",
                format_percent(reconciliation["reconciliation_rate_pct"]),
                help="A key data-quality signal: the share of orders whose recorded "
                "total actually matches the sum of their line items.",
            )

    st.divider()

    # --- F. Payment analytics -------------------------------------------------
    section_header("Payment Analytics")
    col1, col2 = st.columns(2)
    with col1:
        st.caption("Payment Status Distribution")
        pay_status = _safe("payment status distribution", queries.payment_status_distribution, engine)
        if pay_status is not None and not pay_status.empty:
            st.bar_chart(pay_status.set_index("payment_status")["payment_count"])
    with col2:
        st.caption("Payment Method Distribution")
        pay_method = _safe("payment method distribution", queries.payment_method_distribution, engine)
        if pay_method is not None and not pay_method.empty:
            st.bar_chart(pay_method.set_index("payment_method")["payment_count"])
    if revenue is not None:
        st.metric("Revenue from Successful Payments", format_currency(revenue))

    st.divider()

    # --- G. Data quality / pipeline health -------------------------------------
    section_header("Data Quality / Pipeline Health", f"Inspecting load: {selected_batch_id}")
    batch_row = batches[batches["batch_id"] == selected_batch_id].iloc[0]
    health_cols = st.columns(4)
    health_cols[0].metric("Status", batch_row["status"])
    health_cols[1].metric("Loaded Rows", f"{int(batch_row['loaded_row_count'] or 0):,}")
    health_cols[2].metric("Curated Rows", f"{int(batch_row['curated_row_count'] or 0):,}")
    health_cols[3].metric(
        "Loaded At", str(batch_row["completed_at"])[:19] if pd.notna(batch_row["completed_at"]) else "—"
    )

    quality_report_path = rejected_batch_dir(selected_batch_id) / "quality_report.json"
    if quality_report_path.exists():
        try:
            report = json.loads(quality_report_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Could not read quality report for %s: %s", selected_batch_id, exc)
            report = None
        if report is not None:
            st.caption("Validation quality report for this load")
            qc1, qc2, qc3 = st.columns(3)
            qc1.metric("Valid Rows", f"{report['valid_rows']:,}")
            qc2.metric("Rejected Rows", f"{report['rejected_rows']:,}")
            qc3.metric("Quality", format_percent(report["quality_percentage"]))
            if report["rejection_reasons"]:
                with st.expander("Rejection reasons"):
                    reasons_df = pd.DataFrame(
                        sorted(report["rejection_reasons"].items(), key=lambda kv: -kv[1]),
                        columns=["Reason Code", "Count"],
                    )
                    st.dataframe(reasons_df, use_container_width=True, hide_index=True)
    else:
        st.caption(
            "No validation quality report found on disk for this load "
            f"(expected under `data/rejected/batch_id={selected_batch_id}/`)."
        )

    with st.expander("All pipeline loads"):
        st.dataframe(batches, use_container_width=True, hide_index=True)

    st.divider()

    # --- H. Reconciliation details -----------------------------------------
    section_header(
        "Reconciliation Mismatches",
        "Orders whose recorded total doesn't match the sum of their order_items, "
        "largest discrepancy first.",
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
                    "order_date": "Order Date",
                    "source_total_amount": "Source Total",
                    "calculated_total_amount": "Calculated Total",
                    "total_amount_difference": "Difference",
                }
            )
            for col in ("Source Total", "Calculated Total", "Difference"):
                display[col] = display[col].map(format_currency)
            st.dataframe(display, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
