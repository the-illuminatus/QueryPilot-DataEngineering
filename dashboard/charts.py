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
    padding={"left": 4, "right": 12, "top": 6, "bottom": 4},
)

# Vega expression: format an axis/label value as compact INR (₹, lakh, crore)
# so chart ticks read the same way as the KPI cards and tables.
_INR_LABEL_EXPR = (
    "datum.value === 0 ? '₹0'"
    " : abs(datum.value) >= 10000000 ? '₹' + format(datum.value / 10000000, '.2~f') + ' Cr'"
    " : abs(datum.value) >= 100000 ? '₹' + format(datum.value / 100000, '.1~f') + ' L'"
    " : '₹' + format(datum.value, ',')"
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


def revenue_trend(df: pd.DataFrame, *, x: str = "month", y: str = "revenue", height: int = 320) -> alt.Chart:
    data = df.copy()
    data[x] = pd.to_datetime(data[x])
    data["label"] = data[y].map(format_inr_compact)
    data["_is_last"] = data[x] == data[x].max()

    base = alt.Chart(data).encode(
        x=alt.X(f"{x}:T", title=None, axis=alt.Axis(format="%b %Y", labelAngle=0, tickCount="month")),
        y=alt.Y(
            f"{y}:Q",
            title=None,
            axis=alt.Axis(labelExpr=_INR_LABEL_EXPR, tickCount=5, labelPadding=6),
        ),
    )
    area = base.mark_area(
        line={"color": BLUE, "strokeWidth": 2},
        color=alt.Gradient(
            gradient="linear",
            stops=[
                alt.GradientStop(color="rgba(57,135,229,0.03)", offset=0),
                alt.GradientStop(color="rgba(57,135,229,0.32)", offset=1),
            ],
            x1=1, x2=1, y1=1, y2=0,
        ),
    )
    points = base.mark_circle(size=30, color=BLUE, opacity=1).encode(
        tooltip=[
            alt.Tooltip(f"{x}:T", title="Month", format="%B %Y"),
            alt.Tooltip("label:N", title="Collected revenue"),
        ]
    )
    last_label = (
        base.transform_filter(alt.datum._is_last)
        .mark_text(align="right", dx=-8, dy=-10, color=LABEL, fontSize=11, fontWeight="bold")
        .encode(text="label:N")
    )
    return _style(area + points + last_label, height=height)


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
    # Headroom on the right so the value label past the longest bar never clips.
    domain_max = float(data[value].max()) * 1.18 if len(data) else 1.0

    base = alt.Chart(data).encode(
        y=alt.Y(f"{category}:N", sort="-x", title=category_title, axis=alt.Axis(labelLimit=180)),
        x=alt.X(f"{value}:Q", title=None, axis=None, scale=alt.Scale(domain=[0, domain_max], nice=False)),
    )
    bars = base.mark_bar(color=BLUE, cornerRadiusEnd=3).encode(
        tooltip=[
            alt.Tooltip(f"{category}:N", title=category_title or category.replace("_", " ").title()),
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
    domain_max = float(data[value].max()) * 1.12 if len(data) else 1.0

    base = alt.Chart(data).encode(
        x=alt.X(f"{category}:N", sort=order, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y(f"{value}:Q", title=None, axis=None, scale=alt.Scale(domain=[0, domain_max], nice=False)),
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
