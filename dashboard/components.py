"""Reusable Streamlit UI pieces shared across dashboard sections.

Presentation only. The CSS injected by ``inject_theme`` is a small,
restrained set of overrides on top of the Streamlit dark theme
(``.streamlit/config.toml``) -- consistent card surfaces, tighter
vertical rhythm, and a clear section-heading treatment -- not a
re-skin. No component here reads the database.
"""

from __future__ import annotations

from typing import Iterable, Optional, Tuple

import streamlit as st

LINEAGE_STAGES = ["Raw", "Validated", "Curated", "Warehouse"]

_THEME_CSS = """
<style>
:root {
    --qp-border: #21262d;
    --qp-surface: #12161d;
    --qp-muted: #8b949e;
}
.block-container { padding-top: 2.4rem; padding-bottom: 3rem; max-width: 1180px; }

/* Section heading: label + rule, used by section_header() */
.qp-section { margin: 0.4rem 0 0.9rem; }
.qp-section h3 {
    font-size: 0.82rem; font-weight: 600; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--qp-muted); margin: 0 0 0.15rem;
}
.qp-section p { font-size: 0.9rem; color: var(--qp-muted); margin: 0; }
.qp-section .qp-rule { border-bottom: 1px solid var(--qp-border); margin-top: 0.55rem; }

/* KPI cards: st.metric wrapped in a bordered surface */
div[data-testid="stMetric"] {
    background: var(--qp-surface);
    border: 1px solid var(--qp-border);
    border-radius: 10px;
    padding: 0.9rem 1rem 1rem;
}
div[data-testid="stMetric"] label p { font-size: 0.78rem; color: var(--qp-muted); }
div[data-testid="stMetricValue"] { font-size: 1.55rem; font-weight: 600; }

/* Tabs: quieter, evenly spaced */
button[data-baseweb="tab"] { font-size: 0.92rem; }
div[data-testid="stTabs"] div[data-baseweb="tab-list"] { gap: 1.4rem; }

/* Dataframes: flatten the heavy default border */
div[data-testid="stDataFrame"] { border: 1px solid var(--qp-border); border-radius: 8px; }

/* Page title lockup */
.qp-brand { display: flex; align-items: baseline; gap: 0.6rem; margin-bottom: 0.1rem; }
.qp-brand .qp-name { font-size: 1.5rem; font-weight: 700; letter-spacing: -0.01em; }
.qp-brand .qp-kicker {
    font-size: 0.8rem; font-weight: 600; letter-spacing: 0.06em;
    text-transform: uppercase; color: var(--qp-muted);
}
.qp-sub { color: var(--qp-muted); font-size: 0.92rem; margin: 0.15rem 0 0; }
</style>
"""


def inject_theme() -> None:
    st.markdown(_THEME_CSS, unsafe_allow_html=True)


def page_header(name: str, kicker: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="qp-brand">
            <span class="qp-name">{name}</span>
            <span class="qp-kicker">{kicker}</span>
        </div>
        <p class="qp-sub">{subtitle}</p>
        """,
        unsafe_allow_html=True,
    )


def section_header(title: str, description: str = "") -> None:
    desc = f"<p>{description}</p>" if description else ""
    st.markdown(
        f'<div class="qp-section"><h3>{title}</h3>{desc}<div class="qp-rule"></div></div>',
        unsafe_allow_html=True,
    )


def kpi_row(items: Iterable[Tuple[str, str, Optional[str]]]) -> None:
    """items: iterable of (label, value, help_text_or_None)."""
    items = list(items)
    for column, (label, value, help_text) in zip(st.columns(len(items)), items):
        column.metric(label, value, help=help_text)


def lineage_badge(current_stage: str = "Warehouse") -> None:
    parts = [f"**{s}**" if s == current_stage else s for s in LINEAGE_STAGES]
    st.caption("Pipeline lineage · " + " → ".join(parts))


def empty_state(message: str) -> None:
    st.caption(f":grey[{message}]")
