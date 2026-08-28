"""Reusable Streamlit UI pieces shared across dashboard sections.

Presentation only -- no component here reads the database. The only CSS
injected (``inject_theme``) styles this module's *own* markup (the brand
lockup and section headers) plus one page-width rule; card borders,
metric layout, tabs and tables are left to native Streamlit widgets
(``st.metric(border=True)`` etc.) rather than overridden through
generated DOM selectors.
"""

from __future__ import annotations

from typing import Iterable, Sequence, Tuple

import streamlit as st

_THEME_CSS = """
<style>
:root { --qp-border: #262d36; --qp-muted: #8b949e; }

/* Give the page a comfortable reading width and top breathing room. */
.block-container { padding-top: 2.6rem; padding-bottom: 3.5rem; max-width: 1240px; }

/* Section eyebrow: small uppercase label + optional note + hairline rule. */
.qp-section { margin: 1.6rem 0 1rem; }
.qp-section:first-child { margin-top: 0.2rem; }
.qp-section h3 {
    font-size: 0.78rem; font-weight: 600; letter-spacing: 0.09em;
    text-transform: uppercase; color: var(--qp-muted); margin: 0;
}
.qp-section p { font-size: 0.9rem; color: var(--qp-muted); margin: 0.25rem 0 0; max-width: 62ch; }
.qp-section .qp-rule { border-bottom: 1px solid var(--qp-border); margin-top: 0.6rem; }

/* Page title lockup + subordinate metadata line. */
.qp-brand { display: flex; align-items: baseline; gap: 0.7rem; flex-wrap: wrap; margin-bottom: 0.15rem; }
.qp-brand .qp-name { font-size: 1.6rem; font-weight: 700; letter-spacing: -0.01em; }
.qp-brand .qp-kicker {
    font-size: 0.8rem; font-weight: 600; letter-spacing: 0.06em;
    text-transform: uppercase; color: var(--qp-muted);
}
.qp-sub { color: var(--qp-muted); font-size: 0.95rem; margin: 0.1rem 0 0; }
.qp-meta { color: var(--qp-muted); font-size: 0.8rem; margin: 0.5rem 0 0; }
.qp-meta span:not(:last-child)::after { content: "·"; margin: 0 0.55rem; color: var(--qp-border); }
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


def page_meta(items: Sequence[str]) -> None:
    """A single quiet line of context under the header (freshness, dataset
    nature, pipeline lineage) -- present but visually subordinate."""
    spans = "".join(f"<span>{item}</span>" for item in items if item)
    st.markdown(f'<p class="qp-meta">{spans}</p>', unsafe_allow_html=True)


def section_header(title: str, description: str = "") -> None:
    desc = f"<p>{description}</p>" if description else ""
    st.markdown(
        f'<div class="qp-section"><h3>{title}</h3>{desc}<div class="qp-rule"></div></div>',
        unsafe_allow_html=True,
    )


def kpi_row(items: Iterable[Tuple]) -> None:
    """items: iterable of (label, value, help_text_or_None[, chart_data]).
    Each renders as a bordered ``st.metric``; a 4th element, if present, is
    a small trend series shown inside the card."""
    items = list(items)
    for column, item in zip(st.columns(len(items)), items):
        label, value, help_text = item[0], item[1], item[2]
        chart_data = item[3] if len(item) > 3 else None
        column.metric(
            label,
            value,
            help=help_text,
            border=True,
            chart_data=chart_data,
            chart_type="area" if chart_data is not None else None,
        )


def empty_state(message: str) -> None:
    st.caption(f":grey[{message}]")
