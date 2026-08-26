"""Reusable Streamlit UI pieces shared across dashboard sections."""

import streamlit as st

LINEAGE_STAGES = ["Raw", "Validated", "Curated", "Warehouse"]


def format_currency(value: float) -> str:
    return f"${value:,.2f}"


def format_percent(value: float) -> str:
    return f"{value:,.2f}%"


def kpi_row(items) -> None:
    """items: iterable of (label, value, help_text_or_None)."""
    items = list(items)
    columns = st.columns(len(items))
    for column, (label, value, help_text) in zip(columns, items):
        with column:
            st.metric(label, value, help=help_text)


def lineage_badge(current_stage: str = "Warehouse") -> None:
    parts = [f"**{s}**" if s == current_stage else s for s in LINEAGE_STAGES]
    st.caption(" → ".join(parts))


def section_header(title: str, description: str = "") -> None:
    st.subheader(title)
    if description:
        st.caption(description)
