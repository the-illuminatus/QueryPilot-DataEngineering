"""Altair chart builders for the dashboard.

Altair ships with Streamlit (it backs ``st.*_chart``), so using it
directly adds no dependency -- it just buys control over colour,
labels and sorting so every chart on the page reads as one system.

Design rules followed here (see the project's data-viz guidance):
  * One measure per axis, never a dual axis.
  * Magnitude comparisons (revenue by category / state, method mix) use
    a single blue hue -- colour is not carrying identity, length is.
  * State breakdowns (order status, payment status) use the fixed
    status palette, with the value also printed on each bar so meaning
    never rests on colour alone.
  * Legends are omitted where the axis already names each mark.
  * Grid/axis lines stay recessive; the surface is transparent so the
    Streamlit theme shows through.
"""

from __future__ import annotations

import altair as alt
import pandas as pd

from dashboard.format import format_count, format_inr_compact

# Categorical + status hues, taken from the data-viz reference palette
# (dark-surface steps -- the dashboard theme is dark).
BLUE = "#3987e5"
AXIS = "#8b949e"
GRID = "#21262d"
LABEL = "#c9d1d9"

STATUS_COLORS = {
    "good": "#0ca30c",
    "warning": "#fab219",
    "serious": "#ec835a",
    "critical": "#d03b3b",
    "neutral": "#3987e5",
}

ORDER_STATUS_ROLE = {
    "DELIVERED": "good",
    "SHIPPED": "neutral",
    "PLACED": "warning",
    "RETURNED": "serious",
    "CANCELLED": "critical",
}

PAYMENT_STATUS_ROLE = {
    "SUCCESS": "good",
    "PENDING": "warning",
    "REFUNDED": "serious",
    "FAILED": "critical",
}

_BASE_CONFIG = dict(
    background="rgba(0,0,0,0)",
    padding={"left": 4, "right": 12, "top": 4, "bottom": 4},
)


def _style(chart: alt.Chart, *, height: int = 260) -> alt.Chart:
    return (
        chart.properties(height=height)
        .configure_view(strokeWidth=0, fill="rgba(0,0,0,0)")
        .configure(**_BASE_CONFIG)
        .configure_axis(
            labelColor=LABEL,
            titleColor=AXIS,
            gridColor=GRID,
            domainColor=GRID,
            tickColor=GRID,
            labelFontSize=11,
            titleFontSize=11,
            titleFontWeight="normal",
        )
    )


def revenue_trend(df: pd.DataFrame, *, x: str = "month", y: str = "revenue") -> alt.Chart:
    data = df.copy()
    data[x] = pd.to_datetime(data[x])
    data["label"] = data[y].map(format_inr_compact)

    base = alt.Chart(data).encode(
        x=alt.X(f"{x}:T", title=None, axis=alt.Axis(format="%b %Y", labelAngle=0)),
        y=alt.Y(f"{y}:Q", title="Collected revenue (₹)", axis=alt.Axis(format="~s")),
    )
    area = base.mark_area(
        line={"color": BLUE, "strokeWidth": 2},
        color=alt.Gradient(
            gradient="linear",
            stops=[
                alt.GradientStop(color="rgba(57,135,229,0.02)", offset=0),
                alt.GradientStop(color="rgba(57,135,229,0.28)", offset=1),
            ],
            x1=1, x2=1, y1=1, y2=0,
        ),
    )
    points = base.mark_circle(size=34, color=BLUE, opacity=1).encode(
        tooltip=[
            alt.Tooltip(f"{x}:T", title="Month", format="%B %Y"),
            alt.Tooltip("label:N", title="Revenue"),
        ]
    )
    return _style(area + points)


def magnitude_bar(
    df: pd.DataFrame,
    *,
    category: str,
    value: str,
    category_title: str | None = None,
    money: bool = True,
    height: int = 300,
) -> alt.Chart:
    data = df.copy()
    fmt = format_inr_compact if money else format_count
    data["label"] = data[value].map(fmt)

    base = alt.Chart(data).encode(
        y=alt.Y(f"{category}:N", sort="-x", title=category_title),
        x=alt.X(f"{value}:Q", title=None, axis=None),
    )
    bars = base.mark_bar(color=BLUE, cornerRadiusEnd=3).encode(
        tooltip=[
            alt.Tooltip(f"{category}:N", title=category_title or category),
            alt.Tooltip("label:N", title=value.replace("_", " ").title()),
        ]
    )
    text = base.mark_text(align="left", baseline="middle", dx=6, color=LABEL, fontSize=11).encode(
        text="label:N"
    )
    return _style(bars + text, height=height)


def status_bar(
    df: pd.DataFrame,
    *,
    category: str,
    value: str,
    role_map: dict,
    height: int = 260,
) -> alt.Chart:
    data = df.copy()
    data["label"] = data[value].map(format_count)
    data["_color"] = data[category].map(lambda s: STATUS_COLORS[role_map.get(s, "neutral")])
    order = list(role_map.keys())

    base = alt.Chart(data).encode(
        x=alt.X(f"{category}:N", sort=order, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y(f"{value}:Q", title=None, axis=None),
    )
    bars = base.mark_bar(cornerRadiusEnd=3).encode(
        color=alt.Color("_color:N", scale=None, legend=None),
        tooltip=[
            alt.Tooltip(f"{category}:N", title=category.replace("_", " ").title()),
            alt.Tooltip("label:N", title="Count"),
        ],
    )
    text = base.mark_text(baseline="bottom", dy=-4, color=LABEL, fontSize=11).encode(text="label:N")
    return _style(bars + text, height=height)
